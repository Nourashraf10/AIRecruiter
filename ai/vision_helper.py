# ai/vision_helper.py
"""
GPT-4 Vision integration for intelligent UI element detection.
Uses OpenAI's Vision API to analyze screenshots and find elements.
"""

import os
import base64
import requests
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


class VisionHelper:
    """Helper class for GPT-4 Vision-based UI element detection"""
    
    def __init__(self):
        """Initialize Vision Helper with OpenAI API key"""
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def encode_image(self, image_path: str) -> str:
        """
        Encode image to base64 string
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def find_element(self, screenshot_path: str, element_description: str) -> Optional[Dict[str, Any]]:
        """
        Find an element in a screenshot using GPT-4 Vision
        
        Args:
            screenshot_path: Path to the screenshot
            element_description: Natural language description of the element to find
            
        Returns:
            Dictionary with element information (selector, coordinates, etc.) or None
        """
        print(f"🔍 Using AI vision to find: {element_description}")
        
        # Encode the screenshot
        base64_image = self.encode_image(screenshot_path)
        
        # Create the prompt
        prompt = f"""
You are analyzing a web page screenshot to help with browser automation.

Task: Find the element described as "{element_description}"

Please analyze the screenshot and provide:
1. A CSS selector that would uniquely identify this element (if possible)
2. The approximate coordinates (x, y) of the element's center as percentages of the image dimensions
3. The text content of the element (if any)
4. Whether the element is visible and clickable

Respond in JSON format:
{{
    "found": true/false,
    "selector": "CSS selector or null",
    "coordinates": {{"x": percentage, "y": percentage}},
    "text": "element text or null",
    "clickable": true/false,
    "confidence": "high/medium/low",
    "reasoning": "brief explanation"
}}

If the element is not found, set "found" to false and explain why in "reasoning".
"""
        
        # Call GPT-4 Vision API
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": "gpt-4o",  # Using GPT-4o which has vision capabilities
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse JSON response
                import json
                # Extract JSON from markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                element_info = json.loads(content)
                
                if element_info.get('found'):
                    print(f"✅ Element found: {element_info.get('reasoning')}")
                    return element_info
                else:
                    print(f"❌ Element not found: {element_info.get('reasoning')}")
                    return None
            else:
                print(f"❌ Vision API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Vision helper error: {str(e)}")
            return None
    
    def get_element_coordinates(self, screenshot_path: str, element_description: str) -> Optional[Tuple[int, int]]:
        """
        Get pixel coordinates of an element
        
        Args:
            screenshot_path: Path to the screenshot
            element_description: Natural language description of the element
            
        Returns:
            Tuple of (x, y) pixel coordinates or None
        """
        element_info = self.find_element(screenshot_path, element_description)
        
        if not element_info or not element_info.get('found'):
            return None
        
        # Get image dimensions
        from PIL import Image
        with Image.open(screenshot_path) as img:
            width, height = img.size
        
        # Convert percentage coordinates to pixels
        coords = element_info.get('coordinates', {})
        x_percent = coords.get('x', 50)
        y_percent = coords.get('y', 50)
        
        x_pixel = int((x_percent / 100) * width)
        y_pixel = int((y_percent / 100) * height)
        
        return (x_pixel, y_pixel)
    
    def verify_element_state(self, screenshot_path: str, element_description: str, expected_state: str) -> bool:
        """
        Verify if an element is in a specific state
        
        Args:
            screenshot_path: Path to the screenshot
            element_description: Natural language description of the element
            expected_state: Expected state (e.g., "visible", "enabled", "selected")
            
        Returns:
            True if element is in expected state, False otherwise
        """
        print(f"🔍 Verifying element state: {element_description} should be {expected_state}")
        
        base64_image = self.encode_image(screenshot_path)
        
        prompt = f"""
Analyze this screenshot and verify if the element "{element_description}" is in the state: "{expected_state}".

Respond with JSON:
{{
    "verified": true/false,
    "current_state": "description of current state",
    "reasoning": "explanation"
}}
"""
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.1
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                import json
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                verification = json.loads(content)
                verified = verification.get('verified', False)
                
                if verified:
                    print(f"✅ Verified: {verification.get('reasoning')}")
                else:
                    print(f"❌ Not verified: {verification.get('reasoning')}")
                
                return verified
            else:
                print(f"❌ Vision API error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            return False
