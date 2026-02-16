# ai/linkedin_poster.py
"""
LinkedIn job posting automation service.
Handles the complete flow: content generation → login → posting → URL extraction.
"""

import os
import time
import json
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
import requests
from asgiref.sync import sync_to_async

from .browser_agent import BrowserAgent
from .vision_helper import VisionHelper
from .linkedin_job_post_prompt import create_linkedin_job_post_prompt


class LinkedInVacancyPoster:
    """Service class for automating LinkedIn job postings"""
    
    def __init__(self, vacancy, headless: bool = None):
        """
        Initialize LinkedIn poster
        
        Args:
            vacancy: Vacancy model instance
            headless: Run browser in headless mode (defaults to settings)
        """
        self.vacancy = vacancy
        # Force headless mode in Docker containers (no display available)
        is_docker = os.environ.get('DOCKER_CONTAINER', '0') == '1'
        if is_docker:
            self.headless = True
        else:
            self.headless = headless if headless is not None else getattr(settings, 'LINKEDIN_HEADLESS', True)
        
        # Get credentials from settings
        self.linkedin_email = getattr(settings, 'LINKEDIN_EMAIL', '')
        self.linkedin_password = getattr(settings, 'LINKEDIN_PASSWORD', '')
        self.company_page = getattr(settings, 'LINKEDIN_COMPANY_PAGE', '')
        
        # Validate credentials
        if not self.linkedin_email or not self.linkedin_password:
            raise ValueError("LinkedIn credentials not configured. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in settings.")
        
        # Initialize helpers
        self.browser = None
        self.vision_helper = VisionHelper()
        
        # OpenAI API key for content generation
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', os.environ.get('OPENAI_API_KEY'))
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
    
    def generate_job_post_content(self) -> str:
        """
        Generate professional LinkedIn job post content using GPT-4
        
        Returns:
            Generated job post text
        """
        print(f"📝 Generating LinkedIn job post content for: {self.vacancy.title}")
        
        # Create the prompt
        prompt = create_linkedin_job_post_prompt(self.vacancy)
        
        try:
            # Call OpenAI API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert HR professional who creates compelling, professional LinkedIn job postings."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                job_post = result['choices'][0]['message']['content'].strip()
                
                print(f"✅ Generated job post ({len(job_post)} characters)")
                print(f"Preview: {job_post[:200]}...")
                
                return job_post
            else:
                print(f"❌ OpenAI API error: {response.status_code} - {response.text}")
                return self._generate_fallback_content()
                
        except Exception as e:
            print(f"❌ Content generation failed: {str(e)}")
            return self._generate_fallback_content()
    
    def _generate_fallback_content(self) -> str:
        """Generate basic fallback content if GPT fails"""
        return f"""
We're hiring a {self.vacancy.title}!

**About the Role**
Join our {self.vacancy.department} team and make an impact.

**Key Skills**
{self.vacancy.keywords}

**What We're Looking For**
• Strong technical skills
• Team player with excellent communication
• Passion for innovation

**Ready to Apply?**
We'd love to hear from you! Apply now to join our team.
""".strip()
    
    def login_to_linkedin(self) -> bool:
        """
        Login to LinkedIn using browser automation
        
        Returns:
            True if login successful, False otherwise
        """
        print("🔐 Logging into LinkedIn...")
        
        try:
            # Navigate to LinkedIn login page
            self.browser.navigate("https://www.linkedin.com/login")
            self.browser.wait(2)
            
            # Find and fill email field
            self.browser.type_text('input#username', self.linkedin_email)
            
            # Find and fill password field
            self.browser.type_text('input#password', self.linkedin_password)
            
            # Click sign in button
            self.browser.click('button[type="submit"]')
            self.browser.wait(5)
            
            # Check if login was successful
            current_url = self.browser.get_current_url()
            
            if 'feed' in current_url or 'checkpoint' in current_url:
                print("✅ Login successful")
                
                # Handle 2FA if present
                if 'checkpoint' in current_url:
                    print("⚠️ 2FA challenge detected - may require manual intervention")
                    self.browser.take_screenshot("2fa_challenge")
                    # Wait longer for manual 2FA completion
                    self.browser.wait(30)
                
                return True
            else:
                print(f"❌ Login failed - unexpected URL: {current_url}")
                self.browser.take_screenshot("login_failed")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            self.browser.take_screenshot("login_error")
            return False
    
    def post_job_to_linkedin(self, job_content: str) -> Optional[str]:
        """
        Post job to LinkedIn using browser automation
        Follows the free job posting flow: Jobs tab → Post a free job → Multi-step form
        
        Args:
            job_content: Generated job post content
            
        Returns:
            LinkedIn job post URL if successful, None otherwise
        """
        print("📤 Posting job to LinkedIn...")
        
        try:
            # Step 1: Navigate to LinkedIn Jobs page
            print("🔗 Step 1: Navigating to LinkedIn Jobs...")
            self.browser.navigate("https://www.linkedin.com/jobs/", wait_until='domcontentloaded', timeout=30000)
            self.browser.wait(3)
            self.browser.take_screenshot("jobs_page")
            
            # Step 2: Click "Post a free job" in the left sidebar
            print("📝 Step 2: Looking for 'Post a free job' link...")
            post_job_selectors = [
                'a:has-text("Post a free job")',
                'a[href*="job-posting"]',
                'text=Post a free job',
                '[data-test-app-aware-link*="job-posting"]'
            ]
            
            clicked = False
            for selector in post_job_selectors:
                try:
                    if self.browser.is_visible(selector, timeout=3000):
                        print(f"✅ Found 'Post a free job' link: {selector}")
                        self.browser.click(selector)
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                print("⚠️ Could not find 'Post a free job' link, trying direct URL...")
                # Fallback: Navigate directly to job posting page
                self.browser.navigate("https://www.linkedin.com/job-posting/", wait_until='domcontentloaded', timeout=30000)
            
            self.browser.wait(3)
            self.browser.take_screenshot("job_posting_form_page")
            
            # Step 3: Fill in job title using vision helper
            print("📝 Step 3: Filling job title using AI vision...")
            current_url = self.browser.get_current_url()
            print(f"Current URL: {current_url}")
            
            # Take a screenshot for vision analysis
            screenshot_path = self.browser.take_screenshot("job_title_page")
            
            # Use vision helper to find the job title input field
            print("🔍 Using AI vision to locate job title field...")
            element_info = self.vision_helper.find_element(
                screenshot_path, 
                "the job title input field with placeholder 'Add the title you are hiring for'"
            )
            
            title_filled = False
            
            if element_info and element_info.get('found'):
                # Try to use the selector if vision helper found one
                selector = element_info.get('selector')
                coordinates = element_info.get('coordinates')
                
                print(f"✅ Vision helper found job title field")
                print(f"   Selector: {selector}")
                print(f"   Coordinates: {coordinates}")
                
                # Method 1: Try using selector if available
                if selector and selector != "null":
                    try:
                        print(f"🎯 Attempting to fill using selector: {selector}")
                        # Escape single quotes in title for JavaScript
                        escaped_title = self.vacancy.title.replace("'", "\\'")
                        # Use JavaScript to set value directly (wrapped in IIFE)
                        js_fill = f"""
                        (() => {{
                            const input = document.querySelector('{selector}');
                            if (input) {{
                                input.value = '{escaped_title}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                            return false;
                        }})()
                        """
                        result = self.browser.execute_script(js_fill)
                        if result:
                            print(f"✅ Filled job title using selector: {self.vacancy.title}")
                            title_filled = True
                    except Exception as e:
                        print(f"⚠️ Selector method failed: {str(e)}")
                
                # Method 2: If selector failed, try coordinates with JavaScript
                if not title_filled and coordinates:
                    try:
                        x_percent = coordinates.get('x', 50)
                        y_percent = coordinates.get('y', 50)
                        
                        print(f"🎯 Attempting to fill using coordinates: ({x_percent}%, {y_percent}%)")
                        
                        # Escape single quotes in title for JavaScript
                        escaped_title = self.vacancy.title.replace("'", "\\'")
                        # Use JavaScript to find input at coordinates and fill it (wrapped in IIFE)
                        js_fill_coords = f"""
                        (() => {{
                            const x = window.innerWidth * {x_percent / 100};
                            const y = window.innerHeight * {y_percent / 100};
                            const element = document.elementFromPoint(x, y);
                            
                            if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {{
                                element.focus();
                                element.value = '{escaped_title}';
                                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                element.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                return true;
                            }}
                            return false;
                        }})()
                        """
                        result = self.browser.execute_script(js_fill_coords)
                        if result:
                            print(f"✅ Filled job title using coordinates: {self.vacancy.title}")
                            title_filled = True
                    except Exception as e:
                        print(f"⚠️ Coordinates method failed: {str(e)}")
                
                if title_filled:
                    # Trigger blur to validate the field
                    self.browser.execute_script("""
                        const titleInput = document.querySelector('input[placeholder*="hiring for"]');
                        if (titleInput) {
                            titleInput.blur();  // Trigger validation
                            setTimeout(() => titleInput.focus(), 100); // Refocus
                        }
                    """)
                    self.browser.wait(3)  # Increased wait for validation
                    self.browser.take_screenshot("title_filled")
            
            # Fallback: Try CSS selectors
            if not title_filled:
                print("❌ Vision helper could not locate job title field")
                self.browser.take_screenshot("title_field_not_found")
                
                # Fallback: Try CSS selectors as backup
                print("⚠️ Falling back to CSS selectors...")
                title_selectors = [
                    'input[placeholder="Add the title you are hiring for"]',
                    'input[placeholder*="hiring for"]',
                    'input[placeholder*="title" i]',
                    'input[type="text"]',
                    'input[name*="title"]',
                    'input[id*="job-title"]',
                    'input[aria-label*="title" i]',
                ]
                
                title_filled = False
                for selector in title_selectors:
                    try:
                        if self.browser.is_visible(selector):
                            print(f"✅ Found job title field with selector: {selector}")
                            self.browser.type_text(selector, self.vacancy.title, timeout=5000)
                            title_filled = True
                            # Trigger blur to validate the field
                            self.browser.execute_script("""
                                const titleInput = document.querySelector('input[placeholder*="hiring for"]');
                                if (titleInput) {
                                    titleInput.blur();  // Trigger validation
                                    setTimeout(() => titleInput.focus(), 100); // Refocus
                                }
                            """)
                            self.browser.wait(3)  # Increased wait for validation
                            self.browser.take_screenshot("title_filled_fallback")
                            break
                    except Exception as e:
                        print(f"⚠️ Failed with selector {selector}: {str(e)}")
                        continue
                
                if not title_filled:
                    print("❌ Could not find job title field with any method")
                    return None
            
            # Click Continue button using JavaScript
            print("➡️ Step 4: Clicking Continue button...")
            
            # Take screenshot for debugging
            continue_screenshot = self.browser.take_screenshot("before_continue")
            
            # Use JavaScript to find and click the Continue button
            print("🔍 Using JavaScript to locate and click Continue button...")
            js_click_continue = """
            (() => {
                // Find all buttons on the page
                const buttons = Array.from(document.querySelectorAll('button'));
                
                // Look for Continue button by text content
                let continueButton = buttons.find(btn => {
                    const text = btn.textContent.trim().toLowerCase();
                    const isVisible = btn.offsetParent !== null;
                    const isEnabled = !btn.disabled;
                    
                    return text.includes('continue') && isVisible && isEnabled;
                });
                
                // If found, scroll into view and click immediately (no setTimeout)
                if (continueButton) {
                    continueButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    continueButton.click();
                    return true;
                }
                
                // Fallback: Try primary button (usually Continue/Submit)
                const primaryButton = buttons.find(btn => 
                    btn.classList.contains('artdeco-button--primary') &&
                    btn.offsetParent !== null &&
                    !btn.disabled
                );
                
                if (primaryButton) {
                    primaryButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    primaryButton.click();
                    return true;
                }
                
                // Last resort: Try any button with data-test attribute
                const dataTestButton = document.querySelector('button[data-live-test-job-posting-shared-hero-footer-v2__next]');
                if (dataTestButton && !dataTestButton.disabled) {
                    dataTestButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    dataTestButton.click();
                    return true;
                }
                
                return false;
            })()
            """
            
            continue_clicked = False
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries and not continue_clicked:
                try:
                    result = self.browser.execute_script(js_click_continue)
                    if result:
                        print("✅ Continue button clicked successfully via JavaScript")
                        continue_clicked = True
                        # Wait for page navigation
                        self.browser.wait(4)
                        
                        # Check if we hit an error page
                        current_url = self.browser.get_current_url()
                        error_detected = False
                        
                        try:
                            # Check for error page indicators
                            if 'error' in current_url.lower():
                                error_detected = True
                            elif self.browser.is_visible('text="Oops! Something went wrong"', timeout=2000):
                                error_detected = True
                        except:
                            pass
                        
                        if error_detected:
                            print(f"⚠️ LinkedIn error page detected (attempt {retry_count + 1}/{max_retries + 1})")
                            if retry_count < max_retries:
                                print("🔄 Retrying Continue button click...")
                                self.browser.go_back()
                                self.browser.wait(3)
                                continue_clicked = False
                                retry_count += 1
                            else:
                                print("❌ Max retries reached, LinkedIn error persists")
                                return None
                        else:
                            print("✅ Successfully navigated past job title page")
                            break
                    else:
                        print("⚠️ JavaScript could not find Continue button")
                        retry_count += 1
                except Exception as e:
                    print(f"⚠️ JavaScript click failed: {str(e)}")
                    retry_count += 1
            
            if not continue_clicked:
                print("⚠️ Trying Playwright click method...")
                # Try using Playwright's built-in click
                continue_selectors = [
                    'button:has-text("Continue")',
                    'button.artdeco-button--primary:has-text("Continue")',
                    'button[data-live-test-job-posting-shared-hero-footer-v2__next]'
                ]
                
                for selector in continue_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=2000):
                            print(f"✅ Found Continue button with selector: {selector}")
                            self.browser.click(selector)
                            continue_clicked = True
                            break
                    except Exception as e:
                        print(f"⚠️ Failed with selector {selector}: {str(e)}")
                        continue
            
            if not continue_clicked:
                print("⚠️ Could not find Continue button with any method, trying keyboard Enter...")
                # Last resort: Press Enter key
                self.browser.page.keyboard.press('Enter')
            
            self.browser.wait(3)
            self.browser.take_screenshot("after_continue")
            
            # Now we're on the multi-step form - fill remaining fields
            print("📋 Step 5: Filling remaining job details...")
            
            # Fill company name (if field exists)
            print("🏢 Looking for company field...")
            try:
                company_selectors = [
                    'input[name*="company"]',
                    'input[placeholder*="company" i]',
                    'input[aria-label*="company" i]'
                ]
                for selector in company_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=2000):
                            company_name = self.company_page.split('/')[-1] if self.company_page else "Bit68"
                            self.browser.type_text(selector, company_name, timeout=5000)
                            print(f"✅ Filled company: {company_name}")
                            self.browser.wait(1)
                            break
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Company field not found or error: {str(e)}")
            
            # Fill location
            print("📍 Looking for location field...")
            try:
                location_selectors = [
                    'input[name*="location"]',
                    'input[placeholder*="location" i]',
                    'input[aria-label*="location" i]',
                    'input[placeholder*="city" i]'
                ]
                for selector in location_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=2000):
                            self.browser.type_text(selector, "Cairo, Egypt", timeout=5000)
                            print("✅ Filled location: Cairo, Egypt")
                            self.browser.wait(2)  # Wait for autocomplete
                            # Try to select first autocomplete option
                            try:
                                self.browser.execute_script("""
                                    var event = new KeyboardEvent('keydown', {key: 'ArrowDown'});
                                    document.activeElement.dispatchEvent(event);
                                    setTimeout(() => {
                                        var enterEvent = new KeyboardEvent('keydown', {key: 'Enter'});
                                        document.activeElement.dispatchEvent(enterEvent);
                                    }, 500);
                                """)
                                self.browser.wait(1)
                            except:
                                pass
                            break
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Location field not found or error: {str(e)}")
            
            self.browser.take_screenshot("location_filled")
            
            # Select workplace type (Remote/Hybrid/On-site)
            print("🏠 Looking for workplace type...")
            try:
                # Try radio buttons first
                remote_selectors = [
                    'input[value="REMOTE"]',
                    'input[value="2"]',  # Sometimes Remote is value 2
                    'label:has-text("Remote")',
                ]
                for selector in remote_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=2000):
                            self.browser.click(selector)
                            print("✅ Selected workplace type: Remote")
                            self.browser.wait(1)
                            break
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Workplace type not found or error: {str(e)}")
            
            # Select job type (Full-time/Part-time/Contract)
            print("💼 Looking for job type...")
            try:
                fulltime_selectors = [
                    'input[value="FULL_TIME"]',
                    'input[value="F"]',
                    'label:has-text("Full-time")',
                    'select[name*="jobType"]'
                ]
                for selector in fulltime_selectors:
                    try:
                        if 'select' in selector:
                            if self.browser.is_visible(selector, timeout=2000):
                                self.browser.select_option(selector, 'FULL_TIME')
                                print("✅ Selected job type: Full-time")
                                break
                        else:
                            if self.browser.is_visible(selector, timeout=2000):
                                self.browser.click(selector)
                                print("✅ Selected job type: Full-time")
                                self.browser.wait(1)
                                break
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Job type not found or error: {str(e)}")
            
            self.browser.take_screenshot("job_details_filled")
            
            # Fill job description
            print("📄 Looking for job description field...")
            try:
                description_selectors = [
                    'textarea[name*="description"]',
                    'textarea[placeholder*="description" i]',
                    'div[contenteditable="true"]',
                    'div[role="textbox"]',
                    'textarea[aria-label*="description" i]'
                ]
                
                description_filled = False
                for selector in description_selectors:
                    try:
                        if self.browser.is_visible(selector):
                            print(f"✅ Found description field: {selector}")
                            
                            if 'contenteditable' in selector or 'textbox' in selector:
                                # Rich text editor
                                self.browser.click(selector)
                                self.browser.wait(0.5)
                                # Use plain text for rich editors
                                escaped_content = job_content.replace('\n', '<br>')
                                script = f'''
                                    var element = document.querySelector('{selector}');
                                    if (element) {{
                                        element.innerHTML = `{escaped_content}`;
                                        element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    }}
                                '''
                                self.browser.execute_script(script)
                            else:
                                # Regular textarea
                                self.browser.type_text(selector, job_content, timeout=5000)
                            
                            description_filled = True
                            print("✅ Filled job description")
                            self.browser.wait(1)
                            break
                    except Exception as e:
                        print(f"⚠️ Failed with selector {selector}: {str(e)}")
                        continue
                
                if not description_filled:
                    print("⚠️ Could not fill description field")
            except Exception as e:
                print(f"⚠️ Description field error: {str(e)}")
            
            self.browser.take_screenshot("description_filled")
            self.browser.wait(2)
            self.browser.take_screenshot("job_form_filled")
            
            # Click "Review" or "Post job" or "Continue" to submit
            print("🚀 Step 6: Submitting job post...")
            submit_selectors = [
                'button:has-text("Post job")',
                'button:has-text("Post")',
                'button:has-text("Review")',
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button[type="submit"]',
                'button[data-test-modal-id*="post"]'
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    if self.browser.is_visible(selector, timeout=3000):
                        print(f"✅ Found submit button: {selector}")
                        self.browser.click(selector)
                        submitted = True
                        self.browser.wait(5)  # Wait for submission
                        break
                except:
                    continue
            
            if not submitted:
                print("⚠️ Could not find submit button with Playwright selectors, trying JavaScript...")
                try:
                    # Use JavaScript to find and click Continue/Submit button
                    js_click_submit = """
                    (() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        
                        // Look for Continue, Post, Review, or Next button
                        const submitButton = buttons.find(btn => {
                            const text = btn.textContent.trim().toLowerCase();
                            const isVisible = btn.offsetParent !== null;
                            const isEnabled = !btn.disabled;
                            const isPrimary = btn.classList.contains('artdeco-button--primary');
                            
                            return (text.includes('continue') || text.includes('post') || 
                                    text.includes('review') || text.includes('next')) && 
                                   isVisible && isEnabled;
                        });
                        
                        if (submitButton) {
                            submitButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            setTimeout(() => {
                                submitButton.click();
                            }, 500);
                            return true;
                        }
                        return false;
                    })()
                    """
                    
                    result = self.browser.execute_script(js_click_submit)
                    if result:
                        print("✅ Submit button clicked successfully via JavaScript")
                        self.browser.wait(6)  # Wait for setTimeout + submission
                        submitted = True
                except Exception as e:
                    print(f"❌ Could not submit form: {str(e)}")
            
            self.browser.take_screenshot("job_posted")
            
            # Step 7: Handle job settings review page (if present)
            print("🔍 Step 7: Checking for job settings review page...")
            current_url = self.browser.get_current_url()
            
            # If we're on the review page, we need to click Continue one more time
            if 'review' in current_url.lower() or 'settings' in current_url.lower():
                print("📋 Job settings review page detected, clicking final Continue...")
                self.browser.wait(2)
                
                # Try to click the final Continue button
                final_continue_clicked = False
                
                # Try Playwright selectors first
                final_continue_selectors = [
                    'button:has-text("Continue")',
                    'button:has-text("Post job")',
                    'button:has-text("Post")',
                    'button.artdeco-button--primary:has-text("Continue")',
                    'button[type="submit"]'
                ]
                
                for selector in final_continue_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=3000):
                            print(f"✅ Found final Continue button: {selector}")
                            self.browser.click(selector)
                            final_continue_clicked = True
                            self.browser.wait(5)
                            break
                    except:
                        continue
                
                # Fallback to JavaScript if Playwright fails
                if not final_continue_clicked:
                    print("⚠️ Trying JavaScript for final Continue button...")
                    try:
                        js_final_continue = """
                        (() => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const continueBtn = buttons.find(btn => {
                                const text = btn.textContent.trim().toLowerCase();
                                return (text.includes('continue') || text.includes('post')) &&
                                       btn.offsetParent !== null && !btn.disabled;
                            });
                            if (continueBtn) {
                                continueBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                setTimeout(() => { continueBtn.click(); }, 500);
                                return true;
                            }
                            return false;
                        })()
                        """
                        result = self.browser.execute_script(js_final_continue)
                        if result:
                            print("✅ Final Continue button clicked via JavaScript")
                            self.browser.wait(6)
                            final_continue_clicked = True
                    except Exception as e:
                        print(f"⚠️ Could not click final Continue: {str(e)}")
                
                if final_continue_clicked:
                    self.browser.take_screenshot("final_submission")
                    print("✅ Job settings reviewed and submitted")
            
            # Step 8: Handle promotion page (Post without promoting)
            print("🔍 Step 8: Checking for promotion page...")
            self.browser.wait(3)  # Wait for page to load
            current_url = self.browser.get_current_url()
            
            # Check if we're on the promotion/payment page
            if 'promote' in current_url.lower() or 'payment' in current_url.lower():
                print("💰 Promotion page detected, clicking 'Post without promoting'...")
                
                post_without_promoting_clicked = False
                
                # Try to find and click "Post without promoting" button
                post_selectors = [
                    'button:has-text("Post without promoting")',
                    'button:has-text("Post without")',
                    'button:has-text("Skip")',
                    'a:has-text("Post without promoting")',
                    'button[data-test-modal-close-btn]'
                ]
                
                for selector in post_selectors:
                    try:
                        if self.browser.is_visible(selector, timeout=3000):
                            print(f"✅ Found 'Post without promoting' button: {selector}")
                            self.browser.click(selector)
                            post_without_promoting_clicked = True
                            self.browser.wait(5)
                            break
                    except:
                        continue
                
                # Fallback to JavaScript if Playwright fails
                if not post_without_promoting_clicked:
                    print("⚠️ Trying JavaScript to find 'Post without promoting' button...")
                    try:
                        js_post_without_promoting = """
                        (() => {
                            const buttons = Array.from(document.querySelectorAll('button, a'));
                            const postBtn = buttons.find(btn => {
                                const text = btn.textContent.trim().toLowerCase();
                                return text.includes('post without') && 
                                       btn.offsetParent !== null && !btn.disabled;
                            });
                            if (postBtn) {
                                postBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                setTimeout(() => { postBtn.click(); }, 500);
                                return true;
                            }
                            return false;
                        })()
                        """
                        result = self.browser.execute_script(js_post_without_promoting)
                        if result:
                            print("✅ 'Post without promoting' clicked via JavaScript")
                            self.browser.wait(6)
                            post_without_promoting_clicked = True
                    except Exception as e:
                        print(f"⚠️ Could not click 'Post without promoting': {str(e)}")
                
                if post_without_promoting_clicked:
                    self.browser.take_screenshot("posted_without_promotion")
                    print("✅ Job posted without promotion!")
            
            # Extract the job URL
            current_url = self.browser.get_current_url()
            print(f"📍 Current URL after posting: {current_url}")
            
            # LinkedIn job URLs typically look like:
            # https://www.linkedin.com/jobs/view/123456789/
            # or https://www.linkedin.com/job-posting/123456789/
            if 'job' in current_url.lower():
                print(f"✅ Job posted successfully: {current_url}")
                return current_url
            else:
                # Try to find the job URL in the page
                print("🔍 Looking for job URL in page...")
                try:
                    # Look for success message or job link
                    job_url_script = """
                        var links = document.querySelectorAll('a[href*="/jobs/view/"], a[href*="/job-posting/"]');
                        if (links.length > 0) {
                            return links[0].href;
                        }
                        return window.location.href;
                    """
                    job_url = self.browser.execute_script(job_url_script)
                    if job_url and 'job' in job_url.lower():
                        print(f"✅ Found job URL: {job_url}")
                        return job_url
                except:
                    pass
                
                print(f"⚠️ Job may be posted but URL unclear: {current_url}")
                return current_url
                
        except Exception as e:
            print(f"❌ Job posting error: {str(e)}")
            self.browser.take_screenshot("posting_error")
            return None
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the complete LinkedIn posting workflow
        
        Returns:
            Dictionary with success status, URL, and any errors
        """
        result = {
            'success': False,
            'url': None,
            'error': None,
            'job_content': None
        }
        
        try:
            # Check if LinkedIn posting is enabled
            if not getattr(settings, 'LINKEDIN_POSTING_ENABLED', False):
                result['error'] = "LinkedIn posting is disabled in settings"
                print(f"⚠️ {result['error']}")
                return result
            
            # Step 1: Generate job post content
            job_content = self.generate_job_post_content()
            result['job_content'] = job_content
            
            # Step 2: Start browser
            self.browser = BrowserAgent(headless=self.headless, screenshots_dir=f"screenshots/vacancy_{self.vacancy.id}")
            self.browser.start()
            
            # Step 3: Login to LinkedIn
            if not self.login_to_linkedin():
                result['error'] = "LinkedIn login failed"
                return result
            
            # Step 4: Post job
            job_url = self.post_job_to_linkedin(job_content)
            
            if job_url:
                result['success'] = True
                result['url'] = job_url
                
                # Update vacancy record (use try-except to handle both sync and async contexts)
                try:
                    self.vacancy.linkedin_url = job_url
                    self.vacancy.linkedin_posted_at = timezone.now()
                    self.vacancy.status = 'collecting_applications'
                    self.vacancy.save(update_fields=['linkedin_url', 'linkedin_posted_at', 'status'])
                    print(f"✅ Vacancy updated with LinkedIn URL")
                except Exception as save_error:
                    # If we're in async context, log but don't fail
                    print(f"⚠️ Could not save vacancy in current context: {str(save_error)}")
                    print(f"ℹ️ Job URL will need to be saved manually: {job_url}")
                    # Store URL in result so caller can save it
                    result['needs_manual_save'] = True
            else:
                result['error'] = "Failed to post job to LinkedIn"
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Execution error: {str(e)}")
            import traceback
            traceback.print_exc()
            return result
            
        finally:
            # Always stop the browser
            if self.browser:
                self.browser.stop()
