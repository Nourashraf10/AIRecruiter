# ai/browser_agent.py
"""
Base browser automation class using Playwright.
Provides core functionality for browser control, navigation, and element interaction.
"""

import os
import time
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from pathlib import Path


class BrowserAgent:
    """Base class for browser automation using Playwright"""
    
    def __init__(self, headless: bool = True, screenshots_dir: Optional[str] = None):
        """
        Initialize browser agent
        
        Args:
            headless: Run browser in headless mode (no UI)
            screenshots_dir: Directory to save screenshots for debugging
        """
        self.headless = headless
        self.screenshots_dir = screenshots_dir or "screenshots"
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._screenshot_counter = 0
        
        # Create screenshots directory if it doesn't exist
        Path(self.screenshots_dir).mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start the browser"""
        print(f"🌐 Starting browser (headless={self.headless})...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()
        print("✅ Browser started successfully")
    
    def stop(self):
        """Stop the browser and cleanup"""
        print("🛑 Stopping browser...")
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("✅ Browser stopped")
    
    def navigate(self, url: str, wait_until: str = 'networkidle', timeout: int = 60000):
        """
        Navigate to a URL
        
        Args:
            url: URL to navigate to
            wait_until: When to consider navigation succeeded ('load', 'domcontentloaded', 'networkidle')
            timeout: Maximum time to wait in milliseconds
        """
        print(f"🔗 Navigating to: {url}")
        try:
            self.page.goto(url, wait_until=wait_until, timeout=timeout)
        except Exception as e:
            print(f"Navigation error: {str(e)}")
            raise
        self.take_screenshot(f"navigate_{url.split('/')[-1]}")
    
    def take_screenshot(self, name: str = None) -> str:
        """
        Take a screenshot of the current page
        
        Args:
            name: Optional name for the screenshot
            
        Returns:
            Path to the saved screenshot
        """
        if not self.page:
            return ""
        
        self._screenshot_counter += 1
        if name:
            filename = f"{self._screenshot_counter:03d}_{name}.png"
        else:
            filename = f"{self._screenshot_counter:03d}_screenshot.png"
        
        filepath = os.path.join(self.screenshots_dir, filename)
        self.page.screenshot(path=filepath, full_page=True)
        print(f"📸 Screenshot saved: {filepath}")
        return filepath
    
    def wait(self, seconds: float):
        """Wait for a specified number of seconds"""
        print(f"⏳ Waiting {seconds} seconds...")
        time.sleep(seconds)
    
    def wait_for_selector(self, selector: str, timeout: int = 30000):
        """
        Wait for an element to appear
        
        Args:
            selector: CSS selector
            timeout: Maximum time to wait in milliseconds
        """
        print(f"⏳ Waiting for selector: {selector}")
        self.page.wait_for_selector(selector, timeout=timeout)
    
    def click(self, selector: str, timeout: int = 30000):
        """
        Click an element
        
        Args:
            selector: CSS selector
            timeout: Maximum time to wait for element
        """
        print(f"🖱️  Clicking: {selector}")
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.click(selector)
        self.wait(0.5)  # Small delay after click
    
    def click_at_coordinates(self, x: int, y: int):
        """
        Click at specific pixel coordinates
        
        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
        """
        print(f"🖱️  Clicking at coordinates: ({x}, {y})")
        self.page.mouse.click(x, y)
        self.wait(0.5)  # Small delay after click
    
    def type_text(self, selector: str, text: str, timeout: int = 30000, delay: int = 50):
        """
        Type text into an input field
        
        Args:
            selector: CSS selector
            text: Text to type
            timeout: Maximum time to wait for element
            delay: Delay between keystrokes in milliseconds
        """
        print(f"⌨️  Typing into {selector}: {text[:50]}...")
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.fill(selector, text)
        self.wait(0.3)
    
    def select_option(self, selector: str, value: str, timeout: int = 30000):
        """
        Select an option from a dropdown
        
        Args:
            selector: CSS selector for the select element
            value: Value to select
            timeout: Maximum time to wait for element
        """
        print(f"📋 Selecting option '{value}' in {selector}")
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.select_option(selector, value)
        self.wait(0.3)
    
    def get_text(self, selector: str, timeout: int = 30000) -> str:
        """
        Get text content of an element
        
        Args:
            selector: CSS selector
            timeout: Maximum time to wait for element
            
        Returns:
            Text content of the element
        """
        self.page.wait_for_selector(selector, timeout=timeout)
        return self.page.text_content(selector)
    
    def is_visible(self, selector: str) -> bool:
        """
        Check if an element is visible
        
        Args:
            selector: CSS selector
            
        Returns:
            True if element is visible, False otherwise
        """
        try:
            return self.page.is_visible(selector, timeout=5000)
        except:
            return False
    
    def execute_script(self, script: str) -> Any:
        """
        Execute JavaScript in the page context
        
        Args:
            script: JavaScript code to execute
            
        Returns:
            Result of the script execution
        """
        return self.page.evaluate(script)
    
    def get_current_url(self) -> str:
        """Get the current page URL"""
        return self.page.url if self.page else ""
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
