"""
Agent module for ZimmerBot
Handles intent detection, date/cabin extraction, and response generation
"""

import re
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta


class Agent:
    """AI Agent for handling customer conversations"""
    
    def detect_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> tuple[str, float, List[str]]:
        """
        Detect user intent from message
        Returns: (intent, confidence, actions)
        """
        message_lower = message.lower()
        context = context or {}
        
        # Intent keywords - מורחב עם כל המילים האפשריות
        intent_keywords = {
            'availability': ['זמינות', 'פנוי', 'פנויה', 'זמין', 'available', 'availability', 'free', 'vacant', 'בדוק זמינות', 'מה זמין'],
            'quote': ['מחיר', 'כמה', 'עולה', 'תמחור', 'price', 'cost', 'quote', 'הצעת מחיר', 'תמחיר', 'כמה עולה'],
            'hold': ['שריין', 'הזמנה', 'להזמין', 'hold', 'reserve', 'book', 'תשריין', 'תשריין', 'שריינתי', 'שריינת', 'שריינו', 'שריינו לי', 'תשריין לי', 'תשריין לי את', 'שריין לי', 'שריין לי את'],
            'book': ['אישור', 'לאשר', 'לסיים', 'confirm', 'approve', 'complete', 'אשר', 'אישרתי', 'מאשר', 'מאושר'],
            'cabin_info': ['תמונה', 'תמונות', 'מידע', 'כתובת', 'תכונות', 'פרטים', 'אודות', 'מה יש', 'מה כולל',
                          'image', 'info', 'address', 'features', 'details', 'about', 'תראה לי', 'תראה', 'אפשר לראות'],
            'location': ['מיקום', 'איפה', 'כתובת', 'מפה', 'maps', 'waze', 'גוגל מפות', 'וייז', 'location', 'address', 'איך מגיעים', 'שלח מיקום', 'שלח לי מיקום', 'איפה המקום', 'איפה הצימר', 'איפה זה', 'קישור למקום', 'מיקום הצימר', 'איפה נמצא', 'איפה נמצא הצימר', 'איפה נמצא המקום'],
            'list_cabins': ['רשימה', 'כל הצימרים', 'שמות', 'list', 'all cabins', 'names', 'מה הצימרים', 'איזה צימרים', 'רשימת צימרים'],
            'greeting': ['שלום', 'היי', 'בוקר', 'ערב', 'hello', 'hi', 'hey'],
            'confirm': ['כן', 'אוקיי', 'בסדר', 'בוא', 'בואו', 'יאללה', 'yes', 'ok', 'okay', 'אני רוצה', 'אני רוצה להזמין', 'בוא נזמין', 'בואו נזמין', 'אני מוכן', 'מוכן', 'בוא נתחיל', 'בואו נתחיל'],
        }
        
        # Calculate intent scores
        intent_scores = {}
        for intent, keywords in intent_keywords.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                intent_scores[intent] = score
        
        # Determine primary intent
        if not intent_scores:
            return ('greeting', 0.5, [])
        
        primary_intent = max(intent_scores.items(), key=lambda x: x[1])[0]
        max_score = intent_scores[primary_intent]
        total_score = sum(intent_scores.values())
        
        confidence = min(0.95, 0.5 + (max_score / max(total_score, 1)) * 0.45)
        
        # Determine actions based on intent
        actions = []
        if primary_intent == 'availability':
            actions = ['availability']
        elif primary_intent == 'quote':
            actions = ['quote']
        elif primary_intent == 'hold':
            actions = ['hold']
        elif primary_intent == 'book':
            actions = ['hold', 'book']
        elif primary_intent == 'cabin_info':
            actions = ['cabin_info']
        elif primary_intent == 'location':
            actions = ['cabin_info']  # Location uses cabin_info to get address
        elif primary_intent == 'list_cabins':
            actions = ['list_cabins']
        elif primary_intent == 'confirm':
            # Check context - if we have quote_confirmed, request customer details
            if context and context.get('booking_flow') and context.get('booking_flow').get('step') == 'quote_confirmed':
                actions = ['customer_details']  # Request customer details form
            elif context and context.get('last_quote'):
                actions = ['customer_details']  # Request customer details form
            else:
                actions = ['book']  # If user confirms, try to book
        elif primary_intent == 'book_now':
            # Check context - if we have quote, request customer details first
            if context and (context.get('last_quote') or (context.get('booking_flow') and context.get('booking_flow').get('step') == 'quote_confirmed')):
                actions = ['customer_details']  # Request customer details form first
            else:
                actions = ['quote']  # Get quote first, not hold directly
        
        # Special handling for short messages that might be context-dependent
        message_words = message_lower.split()
        
        # "תמונה?" or "תמונות?" - always cabin_info if we have cabin_id in context
        if (message_lower.strip() in ['תמונה?', 'תמונה', 'תמונות?', 'תמונות', 'תמונה של', 'תמונות של', 'אפשר לראות תמונה', 'אפשר לראות תמונות'] or
            (any(kw in message_lower for kw in ['תמונה', 'תמונות', 'לראות תמונה']) and len(message_words) <= 4)):
            if context and context.get('cabin_id'):
                primary_intent = 'cabin_info'
                actions = ['cabin_info']
                confidence = 0.9
                return (primary_intent, confidence, actions)
        
        # "כן" or confirmation words - check context for booking flow state
        confirm_keywords = ['כן', 'אוקיי', 'בסדר', 'בוא', 'בואו', 'יאללה', 'yes', 'ok', 'okay', 'אני רוצה', 'אני רוצה להזמין', 'בוא נזמין', 'בואו נזמין', 'אני מוכן', 'מוכן', 'בוא נתחיל', 'בואו נתחיל', 'תזמין', 'תשריין', 'שריין', 'שריין לי', 'תשריין לי']
        if message_lower.strip() in confirm_keywords or any(kw in message_lower for kw in confirm_keywords):
            # Step 1: If we have quote_confirmed → proceed to customer details form
            if context and context.get('booking_flow') and context.get('booking_flow').get('step') == 'quote_confirmed':
                primary_intent = 'confirm'
                actions = ['customer_details']  # Request customer details form
                confidence = 0.95
                return (primary_intent, confidence, actions)
            # Step 1b: If we have last_quote (from metadata) → proceed to customer details form
            elif context and context.get('last_quote'):
                primary_intent = 'confirm'
                actions = ['customer_details']  # Request customer details form
                confidence = 0.9
                return (primary_intent, confidence, actions)
            # Step 2: If we have availability confirmed but no quote yet → get quote
            elif context and context.get('booking_flow') and context.get('booking_flow').get('step') == 'availability_confirmed':
                primary_intent = 'quote'
                actions = ['quote']
                confidence = 0.9
                return (primary_intent, confidence, actions)
            # Step 3: If we have all details → proceed to hold/booking
            elif context and (context.get('cabin_id') and context.get('check_in') and context.get('check_out') and context.get('customer_details')):
                primary_intent = 'book_now'
                actions = ['hold', 'book']
                confidence = 0.9
                return (primary_intent, confidence, actions)
            # Fallback: If we have cabin and dates but no quote → get quote
            elif context and (context.get('cabin_id') and context.get('check_in') and context.get('check_out')):
                primary_intent = 'quote'
                actions = ['quote']
                confidence = 0.8
                return (primary_intent, confidence, actions)
        
        # "תזמין", "תשריין", "עשה הזמנה" - book_now (but check if we have quote first!)
        booking_keywords = ['תזמין', 'עשה הזמנה', 'צור הזמנה', 'בוא נזמין', 'בואו נזמין', 'תעשה הזמנה', 'תשריין', 'שריין', 'שריין לי', 'תשריין לי', 'תשריין לי את', 'שריינתי', 'שריינת', 'שריינו', 'אני רוצה להזמין', 'אני רוצה לשריין']
        if any(kw in message_lower for kw in booking_keywords):
            if context and (context.get('cabin_id') and context.get('check_in') and context.get('check_out')):
                # Check if we have quote_confirmed - if yes, proceed to customer details
                if context.get('booking_flow') and context.get('booking_flow').get('step') == 'quote_confirmed':
                    primary_intent = 'confirm'
                    actions = ['customer_details']  # Request customer details form
                    confidence = 0.95
                    return (primary_intent, confidence, actions)
                # Check if we have quote (from last_quote) - if yes, proceed to customer details
                elif context.get('last_quote'):
                    primary_intent = 'confirm'
                    actions = ['customer_details']  # Request customer details form
                    confidence = 0.9
                    return (primary_intent, confidence, actions)
                # Check if we have availability_confirmed - if yes, get quote
                elif context.get('booking_flow') and context.get('booking_flow').get('step') == 'availability_confirmed':
                    primary_intent = 'quote'
                    actions = ['quote']
                    confidence = 0.9
                    return (primary_intent, confidence, actions)
                # No quote yet - get quote first
                else:
                    primary_intent = 'quote'
                    actions = ['quote']
                    confidence = 0.9
                    return (primary_intent, confidence, actions)
        
        # If we detected a cabin name/id but no clear intent, determine based on message
        extracted_cabin = self.extract_cabin_id(message)
        if extracted_cabin:
            # Update context with extracted cabin (don't override if already set from conversation)
            if context:
                # Only update if not already set or if explicitly mentioned in message
                if 'cabin_id' not in context or any(name in message_lower for name in ['אמי', 'יולי', 'מורן', 'מורני']):
                    context['cabin_id'] = extracted_cabin
            
            # Check if message is asking for price/quote
            price_keywords = ['מחיר', 'כמה', 'עולה', 'תמחור', 'price', 'cost', 'quote']
            if any(kw in message_lower for kw in price_keywords):
                if not actions or 'quote' not in actions:
                    actions = ['quote']
                    primary_intent = 'quote'
                    confidence = 0.8
            else:
                # Check if message is asking for info (contains info keywords or just cabin name)
                info_keywords = ['תמונה', 'תמונות', 'מידע', 'כתובת', 'תכונות', 'פרטים', 'אודות', 'מה יש', 'מה כולל',
                               'image', 'info', 'address', 'features', 'details', 'about']
                if any(kw in message_lower for kw in info_keywords) or len(message.split()) <= 3:
                    if not actions or 'cabin_info' not in actions:
                        actions = ['cabin_info']
                        primary_intent = 'cabin_info'
                        confidence = 0.8
        
        return (primary_intent, confidence, actions)
    
    def extract_dates(self, message: str) -> Optional[Dict[str, str]]:
        """
        Extract dates from message
        Supports formats like:
        - "15-17 במרץ" / "15-17 למרץ"
        - "15.3" / "15.3.26" / "15.3.2026"
        - "2.7.26" (יום.חודש.שנה)
        - "5 למרץ 2026"
        - "15/03/2026"
        - "כל מרץ" / "במהלך מרץ" / "בחודש מרץ" -> entire month
        
        Returns: {'check_in': 'YYYY-MM-DD', 'check_out': 'YYYY-MM-DD', 'is_month_range': bool} or None
        """
        message_lower = message.lower()
        current_year = datetime.now().year
        
        # Check for "entire month" patterns: "כל מרץ", "במהלך מרץ", "בחודש מרץ"
        month_range_patterns = [
            r'כל\s+(ינואר|פברואר|מרץ|מרס|מארס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?:\s+(\d{4}))?',
            r'במהלך\s+(ינואר|פברואר|מרץ|מרס|מארס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?:\s+(\d{4}))?',
            r'בחודש\s+(ינואר|פברואר|מרץ|מרס|מארס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?:\s+(\d{4}))?',
            r'(ינואר|פברואר|מרץ|מרס|מארס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)\s+כולו(?:\s+(\d{4}))?',
        ]
        
        months_he = {
            'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'מרס': 3, 'מארס': 3,
            'אפריל': 4, 'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8,
            'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12
        }
        
        for pattern in month_range_patterns:
            match = re.search(pattern, message_lower)
            if match:
                month_he = match.group(1)
                year_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
                month = months_he.get(month_he)
                if month:
                    year = int(year_str) if year_str else current_year
                    # First day of month
                    check_in = datetime(year, month, 1)
                    # Last day of month
                    if month == 12:
                        check_out = datetime(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        check_out = datetime(year, month + 1, 1) - timedelta(days=1)
                    return {
                        'check_in': check_in.strftime('%Y-%m-%d'),
                        'check_out': check_out.strftime('%Y-%m-%d'),
                        'is_month_range': True,
                        'month': month,
                        'year': year
                    }
        
        # Hebrew month names
        months_he = {
            'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'מרס': 3, 'מארס': 3,
            'אפריל': 4, 'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8,
            'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12
        }
        
        # Pattern 1: "15-17 במרץ" or "15-17 למרץ"
        pattern1 = r'(\d{1,2})[-\s]+(\d{1,2})\s+(?:ב|ל)?(ינואר|פברואר|מרץ|מרס|מארס|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)(?:\s+(\d{4}))?'
        match = re.search(pattern1, message_lower)
        if match:
            day1, day2, month_he, year_str = match.groups()
            month = months_he.get(month_he, 3)
            year = int(year_str) if year_str else current_year
            try:
                check_in = datetime(year, month, int(day1))
                check_out = datetime(year, month, int(day2))
                if check_out < check_in:
                    check_out = check_out + timedelta(days=1)
                return {
                    'check_in': check_in.strftime('%Y-%m-%d'),
                    'check_out': check_out.strftime('%Y-%m-%d')
                }
            except:
                pass
        
        # Pattern 2: "15.3" or "15.3.26" or "15.3.2026" or "15.09.26" (day.month.year)
        pattern2 = r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?'
        matches = list(re.finditer(pattern2, message))
        if len(matches) >= 2:
            # Two dates: check-in and check-out
            match1 = matches[0]
            match2 = matches[1]
            day1, month1, year1_str = match1.groups()
            day2, month2, year2_str = match2.groups()
            
            year1 = int(year1_str) if year1_str else current_year
            if year1 < 100:
                year1 = 2000 + year1 if year1 < 50 else 1900 + year1
            year2 = int(year2_str) if year2_str else year1
            if year2 < 100:
                year2 = 2000 + year2 if year2 < 50 else 1900 + year2
            
            try:
                check_in = datetime(year1, int(month1), int(day1))
                check_out = datetime(year2, int(month2), int(day2))
                if check_out <= check_in:
                    check_out = check_out + timedelta(days=1)
                return {
                    'check_in': check_in.strftime('%Y-%m-%d'),
                    'check_out': check_out.strftime('%Y-%m-%d')
                }
            except:
                pass
        elif len(matches) == 1:
            # Single date: assume check-in, check-out is next day
            match = matches[0]
            day, month, year_str = match.groups()
            year = int(year_str) if year_str else current_year
            if year < 100:
                year = 2000 + year if year < 50 else 1900 + year
            try:
                check_in = datetime(year, int(month), int(day))
                check_out = check_in + timedelta(days=1)
                return {
                    'check_in': check_in.strftime('%Y-%m-%d'),
                    'check_out': check_out.strftime('%Y-%m-%d')
                }
            except:
                pass
        
        # Pattern 3: "15/03/2026" or "15-03-2026"
        pattern3 = r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})'
        matches = list(re.finditer(pattern3, message))
        if len(matches) >= 2:
            match1 = matches[0]
            match2 = matches[1]
            day1, month1, year1 = match1.groups()
            day2, month2, year2 = match2.groups()
            try:
                check_in = datetime(int(year1), int(month1), int(day1))
                check_out = datetime(int(year2), int(month2), int(day2))
                if check_out <= check_in:
                    check_out = check_out + timedelta(days=1)
                return {
                    'check_in': check_in.strftime('%Y-%m-%d'),
                    'check_out': check_out.strftime('%Y-%m-%d')
                }
            except:
                pass
        
        return None
    
    def extract_cabin_id(self, message: str) -> Optional[str]:
        """
        Extract cabin ID from message
        Supports formats like:
        - "ZB01", "ZB02", etc.
        - "צימר של מורן" -> "ZB03"
        - "צימר של יולי" -> "ZB01"
        - "צימר של אמי" -> "ZB02"
        - "אמי" -> "ZB02" (just the name)
        - "יולי" -> "ZB01"
        - "מורן" -> "ZB03"
        
        Returns: cabin_id string or None
        """
        message_lower = message.lower()
        message_clean = re.sub(r'[^\w\s]', ' ', message_lower)  # Remove punctuation
        
        # Direct cabin ID pattern (ZB01, ZB02, etc.)
        pattern = r'\b(ZB\d{2})\b'
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        
        # Cabin name patterns - check for exact word match or in phrase
        # Note: Add new cabin names here when adding new cabins
        cabin_names = {
            'מורן': 'ZB03',
            'מורני': 'ZB03',
            'יולי': 'ZB01',
            'אמי': 'ZB02',
            'ליאה': 'ZB04',  # TODO: Verify this is the correct cabin ID
        }
        
        # Split message into words
        words = message_clean.split()
        
        for name, cabin_id in cabin_names.items():
            # Check if name appears as a word (not part of another word)
            if name in words or f'צימר של {name}' in message_clean or f'צימר {name}' in message_clean:
                return cabin_id
        
        return None
    
    def extract_customer_name(self, message: str) -> Optional[str]:
        """
        Extract customer name from message
        Supports formats like:
        - "על שם משה אופניק"
        - "שם: משה אופניק"
        - "משה אופניק"
        - "name: John Doe"
        
        Returns: customer name string or None
        """
        # Pattern 1: "על שם משה אופניק" or "על שם משה"
        pattern1 = r'על\s+שם\s+([א-ת\s]+?)(?:\s|$|,|\.|-)'
        match = re.search(pattern1, message)
        if match:
            name = match.group(1).strip()
            if len(name) > 1:  # At least 2 characters
                return name
        
        # Pattern 2: "שם: משה אופניק" or "שם משה אופניק"
        pattern2 = r'שם[:\s]+([א-ת\s]+?)(?:\s|$|,|\.|-)'
        match = re.search(pattern2, message)
        if match:
            name = match.group(1).strip()
            if len(name) > 1:
                return name
        
        # Pattern 3: "name: John Doe" or "name John Doe"
        pattern3 = r'name[:\s]+([a-zA-Z\s]+?)(?:\s|$|,|\.|-)'
        match = re.search(pattern3, message.lower())
        if match:
            name = match.group(1).strip()
            if len(name) > 1:
                return name
        
        return None
    
    def generate_response(
        self,
        intent: str,
        actions: List[str],
        context: Optional[Dict[str, Any]] = None,
        tool_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate response based on intent and tool results
        """
        context = context or {}
        tool_results = tool_results or {}
        
        # List cabins
        if intent == 'list_cabins' and 'list_cabins' in tool_results:
            cabins = tool_results['list_cabins']
            if cabins:
                response = "🏡 **רשימת כל הצימרים:**\n\n"
                for cabin in cabins:
                    cabin_id = cabin.get('cabin_id_string') or cabin.get('cabin_id', 'N/A')
                    name = cabin.get('name', 'N/A')
                    area = cabin.get('area', 'N/A')
                    response += f"• {name} ({cabin_id}) - {area}\n"
                return response
            return "לא נמצאו צימרים."
        
        # Cabin info
        if intent == 'cabin_info' and 'cabin_info' in tool_results:
            cabin = tool_results['cabin_info']
            if cabin:
                response = f"🏡 **{cabin.get('name', 'N/A')}**\n"
                response += f"מספר: {cabin.get('cabin_id_string') or cabin.get('cabin_id', 'N/A')}\n"
                if cabin.get('area'):
                    response += f"📍 אזור: {cabin.get('area')}\n"
                
                # Add address if available
                cabin_address = cabin.get('address') or ''
                if cabin_address:
                    response += f"📍 **כתובת:** {cabin_address}\n"
                    # Add Maps/Waze links if available
                    google_maps_url = cabin.get('google_maps_url')
                    waze_url = cabin.get('waze_url')
                    if google_maps_url or waze_url:
                        response += f"🗺️ **מפות:** "
                        links = []
                        if google_maps_url:
                            links.append(f"[Google Maps]({google_maps_url})")
                        if waze_url:
                            links.append(f"[Waze]({waze_url})")
                        response += " • ".join(links) + "\n"
                
                response += "\n"
                
                if cabin.get('description'):
                    response += f"{cabin.get('description')}\n\n"
                
                features = cabin.get('features')
                if features:
                    if isinstance(features, dict):
                        feature_list = [k for k, v in features.items() if v]
                    else:
                        feature_list = str(features).split(',') if isinstance(features, str) else []
                    if feature_list:
                        response += f"✨ תכונות: {', '.join(feature_list[:10])}\n\n"
                
                if cabin.get('max_adults') or cabin.get('max_kids'):
                    response += f"👥 אירוח: עד {cabin.get('max_adults', 0)} מבוגרים"
                    if cabin.get('max_kids'):
                        response += f" ו-{cabin.get('max_kids', 0)} ילדים"
                    response += "\n\n"
                
                images = cabin.get('images_urls') or []
                if images:
                    response += f"📷 תמונות:\n\n"
                    for img_url in images[:3]:  # Limit to 3 images
                        response += f"🖼️ {img_url}\n"
                else:
                    response += "📷 אין תמונות זמינות\n"
                
                return response
            return "לא מצאתי מידע על הצימר."
        
        # Location request
        if intent == 'location' and 'cabin_info' in tool_results:
            cabin = tool_results['cabin_info']
            if cabin:
                # Get full address from tool_results (already built in api_server)
                full_address = cabin.get('address') or ''
                
                # If no address from tool_results, try to build from components
                if not full_address:
                    street = cabin.get('street_name') or ''
                    city = cabin.get('city') or ''
                    postal_code = cabin.get('postal_code') or ''
                    
                    # Convert postal_code to string if needed
                    if postal_code and not isinstance(postal_code, str):
                        postal_code = str(postal_code)
                    
                    # Build full address
                    address_parts = [str(p) for p in [street, city, postal_code] if p]
                    full_address = ', '.join(address_parts)
                
                # Get URLs from tool_results (already built in api_server) or build them
                google_maps_url = cabin.get('google_maps_url')
                waze_url = cabin.get('waze_url')
                
                if not google_maps_url or not waze_url:
                    if full_address:
                        import urllib.parse
                        encoded_address = urllib.parse.quote(full_address)
                        if not google_maps_url:
                            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_address}"
                        if not waze_url:
                            waze_url = f"https://waze.com/ul?q={encoded_address}"
                
                if full_address:
                    response = f"📍 **מיקום הצימר {cabin.get('name', '')}:**\n\n"
                    response += f"**כתובת:** {full_address}\n\n"
                    
                    if google_maps_url or waze_url:
                        response += f"🗺️ **קישורים למפות:**\n"
                        if google_maps_url:
                            response += f"• 🗺️ [Google Maps]({google_maps_url})\n"
                        if waze_url:
                            response += f"• 🧭 [Waze]({waze_url})\n"
                        response += "\n"
                        response += f"💡 לחץ על הקישורים כדי לפתוח במפה או באפליקציית הניווט שלך."
                    
                    return response
                else:
                    return "❌ לא מצאתי כתובת לצימר זה בגוגל שיטס. אנא פנה לבעלים לקבלת פרטים או עדכן את הכתובת ב-Google Sheets."
            return "❌ לא מצאתי מידע על הצימר."
        
        # Availability
        if intent == 'availability':
            # Check if dates are needed
            if tool_results.get('availability_needs_dates'):
                # Try to get cabin_id from context or tool_results
                cabin_id = None
                if context and context.get('cabin_id'):
                    cabin_id = context.get('cabin_id')
                elif tool_results.get('context') and tool_results['context'].get('cabin_id'):
                    cabin_id = tool_results['context'].get('cabin_id')
                
                if cabin_id:
                    return f"אשמח לבדוק זמינות לצימר {cabin_id}. מתי תרצה להגיע? (לדוגמה: 15-17 במרץ או כל מרץ 2026)"
                else:
                    return "אשמח לבדוק זמינות. איזה צימר ובאילו תאריכים? (לדוגמה: 'בדוק לי זמינות בצימר של יולי ב-15-17 במרץ')"
            
            # Check if we have availability results
            if 'availability' in tool_results:
                cabins = tool_results['availability']
                if cabins:
                    # Check if this is a monthly availability (available_dates list)
                    if len(cabins) == 1 and cabins[0].get('available_dates'):
                        cabin = cabins[0]
                        name = cabin.get('name', 'N/A')
                        cabin_id = cabin.get('cabin_id_string') or cabin.get('cabin_id', 'N/A')
                        available_dates = cabin.get('available_dates', [])
                        booked_dates = cabin.get('booked_dates', [])
                        total_available = cabin.get('total_available', 0)
                        total_dates = cabin.get('total_dates_in_range', 0)
                        month_name = tool_results.get('context', {}).get('month_name', 'החודש')
                        
                        if available_dates:
                            response = f"📅 **זמינות {name} ({cabin_id}) - {month_name}:**\n\n"
                            response += f"✅ **תאריכים פנויים:** {total_available} מתוך {total_dates} ימים\n\n"
                            
                            # Format dates nicely - group consecutive dates
                            from datetime import datetime, timedelta
                            dates_parsed = sorted([datetime.strptime(d, '%Y-%m-%d') for d in available_dates])
                            
                            if len(dates_parsed) <= 60:
                                # If 60 dates or less, show all grouped
                                response += "**📋 רשימת תאריכים פנויים:**\n\n"
                                current_group_start = None
                                current_group_end = None
                                groups = []
                                
                                for date in dates_parsed:
                                    if current_group_start is None:
                                        current_group_start = date
                                        current_group_end = date
                                    elif (date - current_group_end).days == 1:
                                        # Consecutive date
                                        current_group_end = date
                                    else:
                                        # Gap found - save previous group
                                        if current_group_start == current_group_end:
                                            groups.append(f"• {current_group_start.strftime('%d.%m.%Y')}")
                                        else:
                                            groups.append(f"• {current_group_start.strftime('%d.%m.%Y')} - {current_group_end.strftime('%d.%m.%Y')} ({((current_group_end - current_group_start).days + 1)} ימים)")
                                        current_group_start = date
                                        current_group_end = date
                                
                                # Output last group
                                if current_group_start is not None:
                                    if current_group_start == current_group_end:
                                        groups.append(f"• {current_group_start.strftime('%d.%m.%Y')}")
                                    else:
                                        groups.append(f"• {current_group_start.strftime('%d.%m.%Y')} - {current_group_end.strftime('%d.%m.%Y')} ({((current_group_end - current_group_start).days + 1)} ימים)")
                                
                                # Display groups (max 20 groups to avoid too long response)
                                for group in groups[:20]:
                                    response += f"{group}\n"
                                
                                if len(groups) > 20:
                                    response += f"\n... ועוד {len(groups) - 20} טווחי תאריכים נוספים\n"
                            else:
                                # Too many dates - show summary
                                response += f"**תאריכים פנויים רבים!**\n"
                                response += f"📅 ראשון: {dates_parsed[0].strftime('%d.%m.%Y')}\n"
                                response += f"📅 אחרון: {dates_parsed[-1].strftime('%d.%m.%Y')}\n"
                                response += f"\n💡 לצפייה בכל התאריכים, ציין טווח תאריכים ספציפי (למשל: '15-17 במרץ')\n"
                            
                            if booked_dates:
                                response += f"\n❌ **תאריכים תפוסים:** {len(booked_dates)} ימים\n"
                            
                            response += "\n💡 **איך להזמין?** ציין תאריכים ספציפיים (למשל: '15-17 במרץ') ואני אכין עבורך הצעת מחיר."
                            
                            return response
                    
                    # Regular availability check (specific dates) - Offer to proceed with booking
                    response = f"✅ מצאתי {len(cabins)} צימרים זמינים בתאריכים שביקשת:\n\n"
                    for cabin in cabins:
                        name = cabin.get('name', 'N/A')
                        cabin_id = cabin.get('cabin_id_string') or cabin.get('cabin_id', 'N/A')
                        area = cabin.get('area', 'N/A')
                        price = cabin.get('total_price', 0) or cabin.get('price', 0)
                        nights = cabin.get('nights', 0)
                        
                        response += f"🏡 {name} ({cabin_id}) - {area}\n"
                        if price:
                            response += f"💰 מחיר: {price}₪ ל-{nights} לילות\n"
                        
                        features = cabin.get('features')
                        if features:
                            if isinstance(features, dict):
                                feature_list = [k for k, v in features.items() if v][:5]
                            else:
                                feature_list = str(features).split(',')[:5] if isinstance(features, str) else []
                            if feature_list:
                                response += f"✨ תכונות: {', '.join(feature_list)}\n"
                        
                        response += "\n"
                    
                    # Offer to proceed with booking process - set booking_flow state
                    if len(cabins) == 1:
                        # Single cabin - set booking_flow state for automatic quote on confirmation
                        cabin = cabins[0]
                        cabin_id = cabin.get('cabin_id_string') or cabin.get('cabin_id', 'N/A')
                        check_in = tool_results.get('context', {}).get('check_in') or context.get('check_in', '')
                        check_out = tool_results.get('context', {}).get('check_out') or context.get('check_out', '')
                        
                        if cabin_id and check_in and check_out:
                            response += "💡 **האם תרצה להמשיך להזמנה?**\n"
                            response += "אם כן, כתוב 'כן' או 'תזמין' ואני אכין עבורך הצעת מחיר מפורטת, ואז נתחיל בתהליך ההזמנה."
                            # Set booking_flow state for single cabin availability
                            tool_results['booking_flow'] = {
                                'step': 'availability_confirmed',
                                'cabin_id': cabin_id,
                                'check_in': check_in,
                                'check_out': check_out
                            }
                        else:
                            response += "💡 **האם תרצה להמשיך להזמנה?**\n"
                            response += "אם כן, כתוב 'כן' או 'תזמין' ואני אכין עבורך הצעת מחיר מפורטת, ואז נתחיל בתהליך ההזמנה."
                    else:
                        # Multiple cabins - user needs to choose
                        response += "💡 **האם תרצה להמשיך להזמנה?**\n"
                        response += "אם כן, בחר צימר וכתוב 'כן' או 'תזמין' ואני אכין עבורך הצעת מחיר מפורטת, ואז נתחיל בתהליך ההזמנה."
                    
                    return response
                return "❌ לא מצאתי צימרים זמינים בתאריכים שביקשת."
        
        # Quote
        if intent == 'quote' and 'quote' in tool_results:
            quote = tool_results['quote']
            if quote:
                cabin_name = quote.get('cabin_name', 'N/A')
                cabin_id = quote.get('cabin_id', 'N/A')
                total = quote.get('total', 0)
                nights = quote.get('nights', 0)
                check_in = quote.get('check_in', '')
                check_out = quote.get('check_out', '')
                
                # Ensure dates are in correct order (check_in < check_out)
                try:
                    from datetime import datetime
                    # Parse dates (handle both date-only and datetime formats)
                    check_in_str = str(check_in).split(' ')[0]  # Get date part only
                    check_out_str = str(check_out).split(' ')[0]  # Get date part only
                    check_in_dt = datetime.fromisoformat(check_in_str)
                    check_out_dt = datetime.fromisoformat(check_out_str)
                    if check_in_dt > check_out_dt:
                        # Dates are reversed - swap them
                        check_in, check_out = check_out, check_in
                except Exception as e:
                    # If parsing fails, use as-is
                    pass
                
                response = f"💰 **הצעת מחיר ל-{cabin_name} ({cabin_id}):**\n\n"
                response += f"📅 **תאריכים:** {check_in} → {check_out}\n"
                response += f"📅 **מספר לילות:** {nights}\n"
                response += f"💵 **סה\"כ:** {total}₪\n\n"
                
                breakdown = quote.get('breakdown', [])
                if breakdown:
                    response += "**פירוט מחיר:**\n"
                    for item in breakdown[:10]:  # Show up to 10 items
                        desc = item.get('description', '')
                        amount = item.get('amount', 0)
                        response += f"• {desc}: {amount}₪\n"
                    response += "\n"
                
                # Offer to proceed with booking - trigger customer details form
                response += "💡 **האם תרצה להזמין?**\n"
                response += "אם כן, כתוב 'כן', 'תזמין', או 'אני רוצה להזמין' ואני אפתח עבורך טופס מילוי פרטים."
                
                # Set flag to trigger customer details form on confirmation
                tool_results['booking_flow'] = {
                    'step': 'quote_confirmed',
                    'cabin_id': cabin_id,
                    'check_in': check_in,
                    'check_out': check_out,
                    'total': total,
                    'nights': nights
                }
                
                return response
            return "❌ לא הצלחתי לחשב מחיר. אנא נסה שוב."
        
        # Hold/Book
        if intent in ['confirm', 'book_now'] and 'hold' in tool_results:
            hold = tool_results['hold']
            if hold:
                hold_id = hold.get('hold_id', 'N/A')
                expires_at = hold.get('expires_at', 'N/A')
                response = f"✅ שריינתי לך את הצימר!\n"
                response += f"🔒 מספר הזמנה: {hold_id}\n"
                response += f"⏰ השריון תקף עד {expires_at}\n"
                return response
            return "❌ לא הצלחתי ליצור שריין."
        
        # Default greeting
        if intent == 'greeting':
            return "שלום! תודה על פנייתך. אני כאן כדי לעזור לך למצוא צימר מתאים. איך אוכל לעזור?"
        
        # Default fallback
        return "אשמח לענות על שאלותיך. מה תרצה לדעת?"
