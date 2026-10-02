"""Custom actions for the bilingual support bot.

Runs on the Rasa action server (`rasa run actions`). Backend calls go to the
order/ticket API at ORDERS_API_URL (mock_api/ locally, any REST service in prod).
"""
import os
import re
from typing import Any, Dict, List, Optional, Text

import requests
from rasa_sdk import Action, FormValidationAction, Tracker, ValidationAction
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

ORDERS_API_URL = os.getenv("ORDERS_API_URL", "http://localhost:8000").rstrip("/")
API_TIMEOUT_S = 5

ARABIC_CHARS = re.compile(r"[؀-ۿ]")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
ORDER_ID_RE = re.compile(r"(?:ORD[-\s]?)?(\d{5})\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?20)?(01[0125]\d{8})")

ISSUE_KEYWORDS = {
    "delivery": ["delivery", "late", "never came", "shipping", "توصيل", "اتأخر", "تأخير", "الشحن", "الشحنة"],
    "payment": ["payment", "charged", "refund", "card", "الدفع", "اتخصم", "فلوس", "الفيزا"],
    "damaged": ["damaged", "broken", "defective", "تالف", "مكسور", "بايظ"],
    "other": ["other", "else", "تانية", "حاجة تانية"],
}

STATUS_TEXT = {
    "processing": {"en": "is being prepared", "ar": "بيتجهز"},
    "shipped": {"en": "has shipped", "ar": "اتشحن"},
    "out_for_delivery": {"en": "is out for delivery", "ar": "خرج مع المندوب"},
    "delivered": {"en": "was delivered", "ar": "اتسلم"},
    "cancelled": {"en": "was cancelled", "ar": "اتلغى"},
}
ETA_AR = {"today": "النهارده", "tomorrow": "بكرة", "in 3 days": "خلال ٣ أيام"}


def _lang(tracker: Tracker) -> Text:
    return tracker.get_slot("lang") or "en"


def _first(value: Any) -> Optional[Text]:
    """Entity slots can arrive as a list when DIET extracts the entity twice."""
    if isinstance(value, list):
        value = value[0] if value else None
    return None if value is None else str(value)


def normalize_order_id(value: Any) -> Optional[Text]:
    text = _first(value)
    if not text:
        return None
    match = ORDER_ID_RE.search(text.translate(ARABIC_DIGITS))
    return f"ORD-{match.group(1)}" if match else None


def normalize_phone(value: Any) -> Optional[Text]:
    text = _first(value)
    if not text:
        return None
    digits = re.sub(r"[\s\-()]", "", text.translate(ARABIC_DIGITS))
    match = PHONE_RE.search(digits)
    return match.group(1) if match else None


def normalize_issue_type(value: Any) -> Optional[Text]:
    text = (_first(value) or "").lower()
    for issue, keywords in ISSUE_KEYWORDS.items():
        if any(k in text for k in keywords):
            return issue
    return None


class ValidatePredefinedSlots(ValidationAction):
    """Runs as action_validate_slot_mappings after every user message.

    Fills the custom-mapped `lang` slot from the script of the latest message, so
    every response (via conditional variations in domain.yml) follows the user's
    language turn by turn, including mid-conversation switches.
    """

    def extract_lang(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        text = tracker.latest_message.get("text") or ""
        if text.startswith("/"):  # button payload: keep the current language
            return {}
        return {"lang": "ar" if ARABIC_CHARS.search(text) else "en"}


class ValidateOrderStatusForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_order_status_form"

    def validate_order_id(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        order_id = normalize_order_id(slot_value)
        if order_id:
            return {"order_id": order_id}
        dispatcher.utter_message(response="utter_invalid_order_id")
        return {"order_id": None}


class ValidateIssueForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_issue_form"

    def validate_issue_type(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        value = _first(slot_value)
        issue = value if value in ISSUE_KEYWORDS else normalize_issue_type(value)
        # Unrecognised free text is still a real complaint: file it as "other".
        return {"issue_type": issue or "other"}

    def validate_phone_number(
        self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        phone = normalize_phone(slot_value)
        if phone:
            return {"phone_number": phone}
        dispatcher.utter_message(response="utter_invalid_phone_number")
        return {"phone_number": None}


class ActionCheckOrderStatus(Action):
    def name(self) -> Text:
        return "action_check_order_status"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        lang = _lang(tracker)
        order_id = tracker.get_slot("order_id")
        try:
            resp = requests.get(f"{ORDERS_API_URL}/orders/{order_id}", timeout=API_TIMEOUT_S)
        except requests.RequestException:
            dispatcher.utter_message(response="utter_api_down")
            return []

        if resp.status_code == 404:
            dispatcher.utter_message(
                text=f"مش لاقي طلب برقم {order_id}. اتأكد من الرقم وجرب تاني."
                if lang == "ar"
                else f"I couldn't find an order with number {order_id}. Please check it and try again."
            )
            return [SlotSet("order_id", None)]
        if not resp.ok:
            dispatcher.utter_message(response="utter_api_down")
            return []

        order = resp.json()
        status = STATUS_TEXT.get(order["status"], {"en": order["status"], "ar": order["status"]})[lang]
        if lang == "ar":
            msg = f"طلبك {order_id} {status}."
            if order.get("eta"):
                eta = ETA_AR.get(order["eta"], order["eta"])
                msg += f" ميعاد التوصيل المتوقع: {eta}."
        else:
            msg = f"Your order {order_id} {status}."
            if order.get("eta"):
                msg += f" Expected delivery: {order['eta']}."
        dispatcher.utter_message(text=msg)
        # Keep order_id so a follow-up complaint can reference it.
        return []


class ActionCreateTicket(Action):
    def name(self) -> Text:
        return "action_create_ticket"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        lang = _lang(tracker)
        payload = {
            "issue_type": tracker.get_slot("issue_type"),
            "phone_number": tracker.get_slot("phone_number"),
            "order_id": tracker.get_slot("order_id"),
            "lang": lang,
            "conversation_id": tracker.sender_id,
        }
        try:
            resp = requests.post(f"{ORDERS_API_URL}/tickets", json=payload, timeout=API_TIMEOUT_S)
            resp.raise_for_status()
        except requests.RequestException:
            dispatcher.utter_message(response="utter_api_down")
            return []

        ticket_id = resp.json()["ticket_id"]
        phone = payload["phone_number"]
        dispatcher.utter_message(
            text=f"اتفتحت شكوى برقم {ticket_id}. فريق الدعم هيكلمك على {phone} خلال ٢٤ ساعة."
            if lang == "ar"
            else f"I've opened ticket {ticket_id}. Our support team will call you on {phone} within 24 hours."
        )
        return [SlotSet("issue_type", None), SlotSet("phone_number", None)]
