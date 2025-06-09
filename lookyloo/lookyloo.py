from pylookyloo import Lookyloo
from time import sleep
import yaml
import io

from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.request import ServiceRequest
from assemblyline_v4_service.common.result import Result, ResultSection, ResultKeyValueSection, ResultImageSection

class LookyLoo(ServiceBase):
    
    def __init__(self, config=None):
        super(LookyLoo, self).__init__(config)
        
    def start(self):
        # Startup actions
        self.log.info(f"start() from {self.service_attributes.name} service called")
        
        self.lookyloo = Lookyloo(root_url="http://127.0.0.1:5100")
        
    def execute(self, request: ServiceRequest) -> None:
        request.result = Result() # Technically not needed, because result is pre-initialized in ServiceBase
        
        # Get the request data
        print(request.file_path)
        with open(request.file_path, 'r') as f:
            data = yaml.safe_load(f)
            
        data.pop("uri")
        
        # Enqueue the URL for processing
        uuid = self.lookyloo.enqueue(url=request.task.fileinfo.uri_info.uri, quiet=True)
        self.log.info(f"Enqueued URL {request.task.fileinfo.uri_info.uri} with UUID {uuid}")
        
        # Wait for the capture to complete
        while self.lookyloo.get_status(uuid)['status_code'] != 1: # 1 means completed
            sleep(1)
        
        self.log.info(f"Capture completed for UUID {uuid}")
        # Retrieve the capture stats
        stats = self.lookyloo.get_capture_stats(uuid)
        
        result_section = ResultKeyValueSection("Result")
        result_section.set_item('LookyLoo UUID', uuid)
        
        # Add the stats to the result section
        for key, value in stats.items():
            result_section.set_item(key, value)
        
        request.result.add_section(result_section)
        
        # Screenshot of visited page
        screenshot = self.lookyloo.get_screenshot(uuid)
        with open('screenshot.png', 'wb') as f:
            f.write(screenshot.read())
        screenshot_section = ResultImageSection(request, title_text="Screenshot of visited page")
        screenshot_section.add_image(
            path='screenshot.png',
            name='screenshot.png',
            description=f"Screenshot of final page visited: {request.task.fileinfo.uri_info.uri}",
        )
        
        screenshot_section.promote_as_screenshot() # This will make it the main screenshot for the request
        request.result.add_section(screenshot_section)
        
        # Cookies section
        if stats.get('total_cookies_received', 0) > 0:
            # Populate cookies if available
            cookies = self.lookyloo.get_cookies(uuid)
            for cookie in cookies:
                cookies_section = ResultKeyValueSection(f"Cookie: {cookie['name']}")
                for key, value in cookie.items():
                    cookies_section.set_item(key, value)
                    
                request.result.add_section(cookies_section)
        

        
            
        