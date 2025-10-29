import requests
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CalendarDiscoveryService:
    """Service for discovering and managing calendar integrations"""
    
    def __init__(self):
        pass
    
    def discover_manager_calendar(self, manager_email: str) -> Dict[str, Any]:
        """
        Discover calendar details for a manager and create/update integration
        
        Args:
            manager_email: Manager's email address
            
        Returns:
            Calendar integration details
        """
        try:
            from .models import CalendarIntegration
            from core.models import User
            
            # Get or create manager user
            manager, created = User.objects.get_or_create(
                email=manager_email,
                defaults={'username': manager_email.split('@')[0].replace('.', '')}
            )
            
            # Check if integration already exists
            try:
                integration = CalendarIntegration.objects.get(manager=manager)
                logger.info(f"Found existing calendar integration for {manager_email}")
                return {
                    'success': True,
                    'created': False,
                    'calendar_details': {
                        'calendar_id': integration.calendar_id,
                        'calendar_uid': integration.calendar_uid,
                        'caldav_url': integration.caldav_url,
                        'is_active': integration.is_active
                    }
                }
            except CalendarIntegration.DoesNotExist:
                # Create new integration with simulated calendar details
                calendar_details = self._simulate_calendar_details(manager_email)
                
                integration = CalendarIntegration.objects.create(
                    manager=manager,
                    calendar_id=calendar_details['calendar_id'],
                    calendar_uid=calendar_details['calendar_uid'],
                    caldav_url=calendar_details['caldav_url'],
                    is_active=True,
                    timezone='UTC'
                )
                
                logger.info(f"Created new calendar integration for {manager_email}")
                return {
                    'success': True,
                    'created': True,
                    'calendar_details': calendar_details
                }
                
        except Exception as e:
            logger.error(f"Error discovering calendar for {manager_email}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _simulate_calendar_details(self, manager_email: str) -> Dict[str, str]:
        """Simulate calendar details for a manager"""
        
        # Generate consistent calendar details based on email
        email_hash = hash(manager_email) % 1000000
        
        return {
            'calendar_id': f"zz{email_hash:06d}",
            'calendar_uid': f"{email_hash:08x}-{email_hash:04x}-{email_hash:04x}-{email_hash:04x}-{email_hash:012x}",
            'caldav_url': f"https://calendar.zoho.com/caldav/{email_hash:08x}-{email_hash:04x}-{email_hash:04x}-{email_hash:04x}-{email_hash:012x}/events/"
        }


class SimpleCalDavClient:
    """Minimal CalDAV client for Zoho to fetch busy events in a date range"""
    def __init__(self, caldav_url: str, username: str, password: str, timeout_seconds: int = 20):
        self.caldav_url = caldav_url.rstrip('/') + '/'
        self.auth = (username, password)
        self.timeout_seconds = timeout_seconds

    def fetch_events_raw(self, start_iso: str, end_iso: str) -> str:
        """Run a CalDAV REPORT to get VEVENTs in range, returns raw XML/ICS multi-status"""
        # REPORT body per RFC 4791 calendar-query
        # Zoho expects ISO timestamps with Z for UTC
        report_xml = f"""
<c:calendar-query xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:d="DAV:">
  <d:prop>
    <d:getetag/>
    <c:calendar-data>
      <c:comp name="VCALENDAR">
        <c:comp name="VEVENT">
          <c:prop name="UID"/>
          <c:prop name="SUMMARY"/>
          <c:prop name="DTSTART"/>
          <c:prop name="DTEND"/>
          <c:prop name="DESCRIPTION"/>
        </c:comp>
      </c:comp>
    </c:calendar-data>
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{start_iso}" end="{end_iso}"/>
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>
""".strip()

        headers = {
            'Content-Type': 'application/xml; charset=utf-8',
            'Depth': '1',
        }
        resp = requests.request(
            method='REPORT',
            url=self.caldav_url,
            headers=headers,
            data=report_xml.encode('utf-8'),
            auth=self.auth,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.text

    def parse_ics_events(self, multistatus_text: str) -> List[Dict[str, Any]]:
        """Extract VEVENT components with DTSTART/DTEND from multistatus text.
        Handles both XML multistatus responses and embedded iCalendar data.
        """
        events: List[Dict[str, Any]] = []
        
        # First try to extract embedded iCalendar data from XML
        if '<c:calendar-data>' in multistatus_text:
            # Extract calendar-data sections
            import re
            calendar_data_matches = re.findall(r'<c:calendar-data><!\[CDATA\[(.*?)\]\]></c:calendar-data>', multistatus_text, re.DOTALL)
            for calendar_data in calendar_data_matches:
                # Parse the embedded iCalendar data
                ics_events = self._parse_ics_text(calendar_data)
                events.extend(ics_events)
        
        # If no embedded data, try to fetch individual event files
        if not events:
            events = self._fetch_individual_events(multistatus_text)
        
        # Fallback: try to parse as direct iCalendar format
        if not events and 'BEGIN:VEVENT' in multistatus_text:
            events = self._parse_ics_text(multistatus_text)
        
        return events
    
    def _fetch_individual_events(self, multistatus_text: str) -> List[Dict[str, Any]]:
        """Fetch individual event files when calendar-data is not embedded."""
        import re
        import requests
        
        events: List[Dict[str, Any]] = []
        
        # Extract event file references - be more specific with the regex
        event_refs = re.findall(r'<D:href>(/caldav/[^<]*\.ics)</D:href>', multistatus_text)
        
        for event_path in event_refs:
            # Construct full URL - the event_path already includes the full path
            # Extract just the filename from the path
            filename = event_path.split('/')[-1]
            event_url = self.caldav_url.rstrip('/') + '/' + filename
            
            try:
                # Fetch the individual event file
                resp = requests.get(event_url, auth=self.auth, timeout=self.timeout_seconds)
                resp.raise_for_status()
                
                # Parse the iCalendar data
                ics_events = self._parse_ics_text(resp.text)
                events.extend(ics_events)
                
            except Exception as e:
                logger.warning(f"Failed to fetch event {event_url}: {e}")
                continue
        
        return events
    
    def _parse_ics_text(self, ics_text: str) -> List[Dict[str, Any]]:
        """Parse iCalendar text format to extract events."""
        events: List[Dict[str, Any]] = []
        # naive split by VEVENT boundaries
        parts = ics_text.split('BEGIN:VEVENT')
        for part in parts[1:]:
            block = 'BEGIN:VEVENT' + part
            if 'END:VEVENT' not in block:
                continue
            block = block.split('END:VEVENT', 1)[0]
            dtstart = None
            dtend = None
            summary = None
            for line in block.splitlines():
                line = line.strip()
                if line.startswith('DTSTART'):
                    # support DTSTART:20250929T100000Z or DTSTART;TZID=...:YYYYMMDDTHHMMSS
                    if ':' in line:
                        value = line.split(':', 1)[1].strip()
                        dtstart = self._parse_ics_datetime(value)
                elif line.startswith('DTEND'):
                    if ':' in line:
                        value = line.split(':', 1)[1].strip()
                        dtend = self._parse_ics_datetime(value)
                elif line.startswith('SUMMARY'):
                    if ':' in line:
                        summary = line.split(':', 1)[1].strip()
            if dtstart and dtend:
                events.append({
                    'start': dtstart, 
                    'end': dtend,
                    'summary': summary or 'No title'
                })
        return events

    def _parse_ics_datetime(self, value: str) -> datetime:
        # Handles Zulu or naive local; default to UTC when Z
        try:
            if value.endswith('Z'):
                return datetime.strptime(value, '%Y%m%dT%H%M%SZ')
            # if has seconds optional
            try:
                return datetime.strptime(value, '%Y%m%dT%H%M%S')
            except Exception:
                return datetime.strptime(value, '%Y%m%d')
        except Exception:
            # fallback: ISO
            return datetime.fromisoformat(value.replace('Z', '+00:00'))