import base64
import gzip
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from time import sleep
from urllib.parse import urlparse

import pylookyloo
import requests
import yaml
from assemblyline.common.identify import Identify
from assemblyline.odm.models.ontology.results.http import HTTP as HTTPResult
from assemblyline.odm.models.ontology.results.network import NetworkConnection
from assemblyline.odm.models.ontology.results.sandbox import Sandbox
from assemblyline_service_utilities.common.tag_helper import add_tag
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.request import ServiceRequest
from assemblyline_v4_service.common.result import (
    Result,
    ResultImageSection,
    ResultKeyValueSection,
    ResultMultiSection,
    ResultSection,
    ResultTableSection,
    ResultTextSection,
    TableRow,
    TableSectionBody,
)
from assemblyline_v4_service.common.task import PARENT_RELATION
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, TooManyRedirects

# Regex from
# https://stackoverflow.com/questions/40939380/how-to-get-file-name-from-content-disposition
# Many tests can be found at http://test.greenbytes.de/tech/tc2231/
UTF8_FILENAME_REGEX = r"filename\*=UTF-8''([\w%\-\.]+)(?:; ?|$)"
ASCII_FILENAME_REGEX = r"filename=([\"']?)(.*?[^\\])\1(?:; ?|$)"


def detect_open_directory(request: ServiceRequest, soup: BeautifulSoup):
    if not soup.title or "index of" not in soup.title.string.lower():
        return

    open_directory_links = []
    open_directory_folders = []
    for a in soup.find_all("a", href=True):
        if "://" in a["href"][:10] and a["href"][0] != ".":
            continue
        if a["href"] == "..":
            # Link to the parent directory
            continue
        if a["href"][0] == "?":
            # Probably just some table ordering
            continue
        if a["href"][0] == "/":
            # Check if it is the root or a parent directory
            if a["href"] == "/" or request.task.fileinfo.uri_info.path.startswith(a["href"]):
                continue

        if a["href"].endswith("/"):
            open_directory_folders.append(a["href"])
        else:
            open_directory_links.append(a["href"])

    if open_directory_links or open_directory_folders:
        open_directory_section = ResultTextSection("Open Directory Detected", parent=request.result)
        if open_directory_links:
            open_directory_section.add_line(f"File{'s' if len(open_directory_links) > 1 else ''}:")

        for link in open_directory_links:
            # Append the full website, remove the '.' from the link
            while link[:2] == "./":
                link = link[2:]
            link = f"{request.task.fileinfo.uri_info.uri.rstrip('/')}/{link}"
            open_directory_section.add_line(link)
            add_tag(open_directory_section, "network.static.uri", link)

        if open_directory_folders:
            open_directory_section.add_line(f"Folder{'s' if len(open_directory_folders) > 1 else ''}:")

        for link in open_directory_folders:
            # Append the full website, remove the '.' from the link
            while link[:2] == "./":
                link = link[2:]
            link = f"{request.task.fileinfo.uri_info.uri.rstrip('/')}/{link}"
            open_directory_section.add_line(link)
            add_tag(open_directory_section, "network.static.uri", link)


def detect_webdav_listing(request: ServiceRequest, content: bytes):
    root = ET.fromstring(content)
    namespace = {"d": "DAV:"}
    links = []
    for response in root.findall("d:response", namespace):
        href = response.find("d:href", namespace)
        if href is not None:
            links.append(href.text)

    if not links:
        return

    webdav_section = ResultTextSection("WebDav Listing Detected", parent=request.result)
    root_url = urlparse(request.task.fileinfo.uri_info.uri)
    root_url = root_url._replace(fragment="")._replace(params="")._replace(query="")._replace(path="").geturl()
    for link in links:
        # Append the root website
        link = f"{root_url}{link}"
        webdav_section.add_line(link)
        add_tag(webdav_section, "network.static.uri", link)


def parse_refresh_header(header_value):
    try:
        refresh = header_value.split(";", 1)
        if int(refresh[0]) <= 15 and refresh[1].startswith("url="):
            return refresh[1][4:]
    except Exception:
        # Maybe log that we weren't able to parse the refresh
        pass
    return ""


class Lookyloo(ServiceBase):
    def start(self):
        self.identify = Identify(use_cache=False)
        self.lookyloo = pylookyloo.Lookyloo(root_url="http://127.0.0.1:5100")
        self.lookyloo_version = (
            subprocess.run(
                ["poetry", "run", "python", "-c", "from importlib.metadata import version; print(version('lookyloo'))"],
                cwd="/opt/lookyloo",
                capture_output=True,
                check=False,
            )
            .stdout.strip()
            .decode("UTF8", errors="backslashreplace")
        )
        self.do_not_download_regexes = [re.compile(x) for x in self.config.get("do_not_download_regexes", [])]
        if not self.lookyloo.is_up:
            subprocess.run("poetry run start".split(), cwd="/opt/lookyloo")
            while not self.lookyloo.is_up:
                sleep(1)
                self.log.info("Waiting for Lookyloo to be up")

    def send_http_request(self, method, request: ServiceRequest, data: dict):
        try:
            with requests.request(
                method,
                request.task.fileinfo.uri_info.uri,
                headers=data.get("headers", {}),
                proxies=self.config["proxies"][request.get_param("proxy")],
                data=data.get("data", None),
                json=data.get("json", None),
                cookies=data.get("cookies", None),
                stream=True,
            ) as r:

                requests_content_path = os.path.join(self.working_directory, "requests_content")
                with open(requests_content_path, "wb") as f:

                    for chunk in r.iter_content(None):
                        f.write(chunk)

                return requests_content_path

        except ConnectionError:
            error_section = ResultTextSection("Error", parent=request.result)
            error_section.add_line(f"Cannot connect to {request.task.fileinfo.uri_info.hostname}")
            error_section.add_line("This server is currently unavailable")
            return None
        except TooManyRedirects as e:
            request.partial()
            error_section = ResultTextSection("Too many redirects", parent=request.result)
            error_section.add_line(f"Cannot connect to {request.task.fileinfo.uri_info.hostname}")

            redirect_section = ResultTableSection("Redirections", parent=error_section)
            for redirect in e.response.history:
                redirect_section.add_row(TableRow({"status": redirect.status_code, "redirecting_url": redirect.url}))
                add_tag(redirect_section, "network.static.uri", redirect.url)
            redirect_section.set_column_order(["status", "redirecting_url"])
            return None

    def execute(self, request: ServiceRequest) -> None:
        request.result = Result()  # Technically not needed, because result is pre-initialized in ServiceBase

        # Get the request data
        with open(request.file_path, "r") as f:
            data = yaml.safe_load(f)

        data.pop("uri")
        for no_dl in self.do_not_download_regexes:
            # Do nothing if we are not supposed to scan that URL
            if no_dl.match(request.task.fileinfo.uri_info.uri):
                return

        method = data.pop("method", "GET")

        if method != "GET":
            # Non-GET request
            requests_content_path = self.send_http_request(method, request, data)

            if not requests_content_path:
                return

            file_info = self.identify.fileinfo(requests_content_path, skip_fuzzy_hashes=True, calculate_entropy=False)
            if file_info["type"].startswith("archive"):
                request.add_extracted(
                    requests_content_path,
                    file_info["sha256"],
                    "Archive from the URI",
                    parent_relation=PARENT_RELATION.DOWNLOADED,
                )
            else:
                request.add_supplementary(
                    requests_content_path,
                    file_info["sha256"],
                    "Full content from the URI",
                    parent_relation=PARENT_RELATION.DOWNLOADED,
                )
            return

        if proxy := self.config["proxies"].get(request.get_param("proxy")):
            if not urlparse(proxy).netloc:
                # If the proxy was written as
                # "127.0.0.1:8080"
                # "user@127.0.0.1:8080"
                # "user:password@127.0.0.1:8080"
                proxy = f"http://{proxy}"

        headers = data.pop("headers", {})
        browser_settings = data.pop("browser_settings", {})
        user_agent = browser_settings.pop("user_agent", None)
        window_size = browser_settings.pop("window_size", None)
        viewport = None
        # Lookyloo doesn't look to support window size modification, only viewport
        if window_size and "x" in window_size:
            w, h = window_size.split("x", 1)
            viewport = {"width": w, "height": h}

        if data or browser_settings:
            ignored_params_section = ResultKeyValueSection("Ignored params", parent=request.result)
            if data:
                ignored_params_section.update_items(data)
            for k, v in browser_settings.items():
                ignored_params_section.set_item(f"browser_settings.{k}", v)

        # Enqueue the URL for processing
        uuid = self.lookyloo.submit(
            quiet=True,
            url=request.task.fileinfo.uri_info.uri,
            user_agent=user_agent,
            proxy=proxy,
            headers=headers,
            viewport=viewport,
        )
        self.log.info(f"Enqueued URL {request.task.fileinfo.uri_info.uri} with UUID {uuid}")

        sandbox_details = {
            "analysis_metadata": {},
            "sandbox_name": "Lookyloo",
            "sandbox_version": self.lookyloo_version,
        }
        if viewport:
            sandbox_details["analysis_metadata"]["window_size"] = f"{viewport['width']}x{viewport['height']}"
        http_result = {}
        target_urls = {request.task.fileinfo.uri_info.uri}

        # Wait for the capture to complete
        while self.lookyloo.get_status(uuid)["status_code"] == 0:  # 0: The capture is queued up but not processed yet
            sleep(1)

        self.log.info(f"URL {request.task.fileinfo.uri_info.uri} with UUID {uuid} is ongoing")
        while self.lookyloo.get_status(uuid)["status_code"] == 2:  # 2: The capture is ongoing and will be ready soon
            sleep(1)

        if self.lookyloo.get_status(uuid)["status_code"] != 1:
            raise Exception("Capture is not ready, an error occured.")

        self.log.info(f"Capture completed for UUID {uuid}")
        # Retrieve the capture stats
        stats = self.lookyloo.get_capture_stats(uuid)

        result_section = ResultKeyValueSection("Result", parent=request.result)
        result_section.set_item("Lookyloo UUID", uuid)

        # Add the stats to the result section
        for key, value in stats.items():
            result_section.set_item(key, value)

        # Cookies section
        if stats.get("total_cookies_received", 0) > 0:
            # Populate cookies if available
            cookies_top_section = ResultSection("Cookies", auto_collapse=True, parent=request.result)
            cookies = self.lookyloo.get_cookies(uuid)
            for cookie in cookies:
                cookies_section = ResultKeyValueSection(f"Cookie: {cookie['name']}", parent=cookies_top_section)
                for key, value in cookie.items():
                    cookies_section.set_item(key, value)

        capture = self.lookyloo.get_complete_capture(uuid)
        with zipfile.ZipFile(capture, "r") as zipped_file:
            zipped_file.extractall(path=os.path.join(self.working_directory, "lookyloo_output"))

        possible_outputs = os.listdir(os.path.join(self.working_directory, "lookyloo_output"))
        assert len(possible_outputs) == 1
        output_folder = os.path.join(self.working_directory, "lookyloo_output", possible_outputs[0])

        screenshot_path = os.path.join(output_folder, "0.png")
        if os.path.exists(screenshot_path):
            screenshot_section = ResultImageSection(
                request, title_text="Screenshot of visited page", parent=request.result
            )
            screenshot_section.add_image(
                path=screenshot_path,
                name="screenshot.png",
                description=f"Screenshot of final page visited: {request.task.fileinfo.uri_info.uri}",
            )
            screenshot_section.promote_as_screenshot()

        favicon_path = os.path.join(output_folder, "0.potential_favicon.ico")
        if os.path.exists(favicon_path):
            favicon_section = ResultImageSection(request, title_text="Favicon of visited page", parent=request.result)
            favicon_section.add_image(
                path=favicon_path,
                name="favicon.ico",
                description=f"Favicon of {request.task.fileinfo.uri_info.uri}",
            )
            fileinfo = self.identify.fileinfo(favicon_path, skip_fuzzy_hashes=True, calculate_entropy=False)
            http_result["favicon"] = {
                "md5": fileinfo["md5"],
                "sha1": fileinfo["sha1"],
                "sha256": fileinfo["sha256"],
                "size": fileinfo["size"],
            }

        if redirects := self.lookyloo.get_redirects(uuid):
            # Since the page can refresh itself, there can be redirect false positives with the same URL
            if redirects["response"]["url"] in redirects["response"]["redirects"]:
                redirects["response"]["redirects"].remove(redirects["response"]["url"])
            if redirects["response"]["redirects"]:
                http_result["redirects"] = []
                redirect_section = ResultKeyValueSection("Redirections", parent=request.result)
                redirect_section.set_item(redirects["response"]["url"], ", ".join(redirects["response"]["redirects"]))
                # add_tag(redirect_section, "network.static.uri", redirecting_url)
                # redirect_section.add_tag("network.static.ip", redirect["redirecting_ip"])
                # add_tag(redirect_section, "network.static.uri", redirect["redirecting_to"])
                for redirect in redirects["response"]["redirects"]:
                    target_urls.add(redirect)
                http_result["redirects"].append(
                    {"from_url": redirects["response"]["url"], "to_url": ", ".join(redirects["response"]["redirects"])}
                )

        source_path = os.path.join(output_folder, "0.html")
        if os.path.exists(source_path):
            with open(source_path, "rb") as f:
                data = f.read()
            soup = BeautifulSoup(data, features="lxml")
            if soup.title and soup.title.string:
                http_result["title"] = soup.title.string

            try:
                detect_open_directory(request, soup)
            except Exception:
                pass

        # Possible duplicate of cookie section
        storage_path = os.path.join(output_folder, "0.storage.json")
        if os.path.exists(storage_path):
            # Populate cookies if available
            with open(storage_path, "rb") as f:
                storage = json.load(f)
            if storage.get("cookies"):
                cookies_section = ResultTableSection("Cookies", auto_collapse=True, parent=request.result)
                for cookie in storage.get("cookies"):
                    cookies_section.add_row(TableRow(**cookie))

        # Find any downloaded file
        with gzip.open(os.path.join(output_folder, "0.har.gz"), "rb") as f:
            har_content = json.load(f)

        for entry in har_content["log"]["pages"]:
            if entry["startedDateTime"]:
                sandbox_details["analysis_metadata"]["start_time"] = entry["startedDateTime"]
                break

        downloads = {}
        redirects = []
        response_errors = []
        for entry in har_content["log"]["entries"]:
            if "response_code" not in http_result:
                http_result["response_code"] = entry["response"]["status"]

            # Convert list of header to a proper dictionary
            request_headers = {header["name"]: header["value"] for header in entry["request"]["headers"]}
            response_headers = {header["name"]: header["value"] for header in entry["response"]["headers"]}

            http_details = {
                "request_uri": entry["request"]["url"],
                # ElasticSearch mappings does not support mapping key starting with :
                # We need to skip Pseudo-Header Fields defined in HTTP/2
                "request_headers": {k: v for k, v in request_headers.items() if not k.startswith(":")},
                "request_method": entry["request"]["method"],
                "response_headers": {k: v for k, v in response_headers.items() if not k.startswith(":")},
                "response_status_code": entry["response"]["status"],
            }

            # Figure out if there is an http redirect
            if entry["response"]["status"] in [301, 302, 303, 307, 308]:
                redirecting_to = ""
                if "redirectURL" in entry["response"]:
                    redirecting_to = entry["response"]["redirectURL"]
                if redirecting_to == "" and "Location" in response_headers:
                    redirecting_to = response_headers["Location"]
                if redirecting_to == "" and "Refresh" in response_headers:
                    if refresh := parse_refresh_header(response_headers["Refresh"]):
                        redirecting_to = refresh
                if redirecting_to == "" and "refresh" in response_headers:
                    if refresh := parse_refresh_header(response_headers["refresh"]):
                        redirecting_to = refresh
                redirects.append(
                    {
                        "status": entry["response"]["status"],
                        "redirecting_url": entry["request"]["url"],
                        "redirecting_ip": (entry["serverIPAddress"] if "serverIPAddress" in entry else "Not Available"),
                        "redirecting_to": redirecting_to if redirecting_to else "Not Available",
                    }
                )

            # Some redirects and hidden in the headers with 200 response codes
            if "refresh" in response_headers:
                if refresh := parse_refresh_header(response_headers["refresh"]):
                    redirects.append(
                        {
                            "status": entry["response"]["status"],
                            "redirecting_url": entry["request"]["url"],
                            "redirecting_ip": (
                                entry["serverIPAddress"] if "serverIPAddress" in entry else "Not Available"
                            ),
                            "redirecting_to": refresh,
                        }
                    )

            # Find all content that was downloaded from the servers
            if "size" in entry["response"]["content"] and entry["response"]["content"]["size"] > 0:
                content_text = entry["response"]["content"].pop("text")
                if "encoding" in entry["response"]["content"] and entry["response"]["content"]["encoding"] == "base64":
                    try:
                        content = base64.b64decode(content_text)
                    except Exception:
                        content = content_text.encode()
                else:
                    content = content_text.encode()

                with tempfile.NamedTemporaryFile(dir=self.working_directory, delete=False, mode="wb") as content_file:
                    content_file.write(content)

                fileinfo = self.identify.fileinfo(content_file.name, skip_fuzzy_hashes=True, calculate_entropy=False)
                content_md5 = fileinfo["md5"]
                entry["response"]["content"]["_replaced"] = fileinfo["sha256"]
                http_details["response_content_fileinfo"] = {
                    "md5": fileinfo["md5"],
                    "sha1": fileinfo["sha1"],
                    "sha256": fileinfo["sha256"],
                    "size": fileinfo["size"],
                }
                if "mimeType" in entry["response"]["content"] and entry["response"]["content"]["mimeType"]:
                    http_details["response_content_mimetype"] = entry["response"]["content"]["mimeType"]

                if content_md5 not in downloads:
                    downloads[content_md5] = {"path": content_file.name}

                # The headers could contain the name of the downloaded file
                if (
                    "Content-Disposition" in response_headers
                    # Some servers are returning an empty "Content-Disposition"
                    and response_headers["Content-Disposition"]
                ):
                    downloads[content_md5]["filename"] = response_headers["Content-Disposition"]
                    match = re.search(ASCII_FILENAME_REGEX, downloads[content_md5]["filename"])
                    if match:
                        downloads[content_md5]["filename"] = match.group(2)

                    match = re.search(UTF8_FILENAME_REGEX, downloads[content_md5]["filename"])
                    if match:
                        downloads[content_md5]["filename"] = match.group(1)
                else:
                    filename = None
                    requested_url = urlparse(entry["request"]["url"])
                    if "." in os.path.basename(requested_url.path):
                        filename = os.path.basename(requested_url.path)

                    if not filename:
                        possible_filename = entry["request"]["url"]
                        if len(possible_filename) > 150:
                            parsed_url = requested_url._replace(fragment="")
                            possible_filename = parsed_url.geturl()

                        if len(possible_filename) > 150:
                            parsed_url = parsed_url._replace(params="")
                            possible_filename = parsed_url.geturl()

                        if len(possible_filename) > 150:
                            parsed_url = parsed_url._replace(query="")
                            possible_filename = parsed_url.geturl()

                        if len(possible_filename) > 150:
                            parsed_url = parsed_url._replace(path="")
                            possible_filename = parsed_url.geturl()
                        filename = possible_filename

                    downloads[content_md5]["filename"] = filename

                if not downloads[content_md5]["filename"]:
                    downloads[content_md5]["filename"] = f"UnknownFilename_{fileinfo['sha256'][:8]}"
                downloads[content_md5]["size"] = entry["response"]["content"]["size"]
                downloads[content_md5]["url"] = entry["request"]["url"]
                downloads[content_md5]["mimeType"] = entry["response"]["content"]["mimeType"]
                downloads[content_md5]["fileinfo"] = fileinfo

                if entry["response"]["status"] == 207 and downloads[content_md5]["mimeType"].startswith("text/xml"):
                    detect_webdav_listing(request, content)

            if "_errorMessage" in entry["response"]:
                response_errors.append((entry["request"]["url"], entry["response"]["_errorMessage"]))

            self.ontology.add_result_part(
                model=NetworkConnection, data={"http_details": http_details, "connection_type": "http"}
            )

        # Add the modified entries log
        modified_har_filepath = os.path.join(self.working_directory, "modified_session.har")
        with open(modified_har_filepath, "w") as f:
            json.dump(har_content, f)

        request.add_supplementary(modified_har_filepath, "session.har", "Complete session log")

        if redirects:
            http_result["redirects"] = []
            redirect_section = ResultMultiSection("Redirections", parent=request.result)
            main_redirection = TableSectionBody()
            secondary_redirection = TableSectionBody()
            for redirect in redirects:
                if redirect["redirecting_url"] in target_urls:
                    target_urls.add(redirect["redirecting_to"])
                    table_body = main_redirection
                else:
                    table_body = secondary_redirection
                table_body.add_row(TableRow(redirect))
                add_tag(redirect_section, "network.static.uri", redirect["redirecting_url"])
                if redirect["redirecting_ip"] != "Not Available":
                    redirect_section.add_tag("network.static.ip", redirect["redirecting_ip"])
                if redirect["redirecting_to"] != "Not Available":
                    add_tag(redirect_section, "network.static.uri", redirect["redirecting_to"])
                http_result["redirects"].append(
                    {"from_url": redirect["redirecting_url"], "to_url": redirect["redirecting_to"]}
                )
            for table_body in [main_redirection, secondary_redirection]:
                if table_body.body:
                    table_body.set_column_order(["status", "redirecting_url", "redirecting_ip", "redirecting_to"])
                    redirect_section.add_section_part(table_body)

        self.ontology.add_result_part(model=Sandbox, data=sandbox_details)
        self.ontology.add_result_part(model=HTTPResult, data=http_result)

        if downloads:
            content_section = ResultTableSection("Downloaded Content")
            safelisted_section = ResultTableSection("Safelisted Content")
            for download_params in downloads.values():
                file_info = download_params["fileinfo"]
                added = True

                if download_params["url"] in target_urls or len(downloads) == 1:
                    added = request.add_extracted(
                        download_params["path"],
                        download_params["filename"],
                        download_params["url"] or "Unknown URL",
                        safelist_interface=self.api_interface,
                        parent_relation=PARENT_RELATION.DOWNLOADED,
                    )
                else:
                    request.add_supplementary(
                        download_params["path"],
                        download_params["filename"],
                        download_params["url"] or "Unknown URL",
                        parent_relation=PARENT_RELATION.DOWNLOADED,
                    )

                (content_section if added else safelisted_section).add_row(
                    TableRow(
                        dict(
                            Filename=download_params["filename"],
                            Size=download_params["size"],
                            mimeType=download_params["mimeType"],
                            url=download_params["url"],
                            SHA256=file_info["sha256"],
                        )
                    )
                )

            if content_section.body:
                request.result.add_section(content_section)
            if safelisted_section.body:
                request.result.add_section(safelisted_section)

        if response_errors:
            error_section = ResultTextSection("Responses Error", parent=request.result)
            for response_url, response_error in response_errors:
                error_section.add_line(f"{response_url}: {response_error}")
