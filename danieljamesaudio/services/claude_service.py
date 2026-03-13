"""
Claude API service for DanielJamesAudio.
Handles equipment identification, fault triage, repair guides, and more.
"""

import base64
import json
import os

# Gracefully handle missing API key
_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            _client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Claude API not available: {e}")
    return _client


def identify_equipment_from_photo(photo_bytes, content_type='image/jpeg'):
    """
    Send a photo to Claude and get equipment identification.

    Returns dict with: make, model, description, estimated_value,
    category_suggestion, subcategory
    """
    client = _get_client()

    image_data = base64.standard_b64encode(photo_bytes).decode('utf-8')

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": content_type,
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": """Identify this audio equipment. You are helping catalogue equipment for a professional sound hire business (Daniel James Audio) in England.

Return ONLY a JSON object with these fields:
{
    "make": "manufacturer name",
    "model": "model name/number",
    "description": "brief description of what it is",
    "estimated_value": estimated current market value in GBP as a number (no currency symbol),
    "category_suggestion": one of "PA Systems", "Backline", "Mixing & Recording", or "Cabling & Accessories",
    "subcategory": "more specific type e.g. Active Speaker, Condenser Microphone, Bass Amplifier"
}

If you cannot identify the equipment, still provide your best guess with lower confidence. Always return valid JSON."""
                }
            ]
        }]
    )

    # Parse the response
    text = message.content[0].text.strip()
    # Handle markdown code blocks
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    return json.loads(text)


def triage_fault(equipment_make, equipment_model, fault_description, manual_text=None):
    """
    Diagnose a fault and recommend repair approach.

    Returns dict with: likely_cause, severity, diy_feasible, repair_steps,
    estimated_cost_range, parts_needed, manual_reference, outsource_recommendation
    """
    client = _get_client()

    context = f"Equipment: {equipment_make} {equipment_model}\nFault: {fault_description}"
    if manual_text:
        context += f"\n\nRelevant service manual excerpt:\n{manual_text[:3000]}"

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""You are an experienced audio equipment repair technician helping a sound hire business owner in England. Diagnose this fault and recommend a repair approach.

{context}

Return ONLY a JSON object:
{{
    "likely_cause": "description of the probable cause",
    "severity": "low|medium|high|critical",
    "diy_feasible": true or false,
    "diy_difficulty": "easy|moderate|advanced",
    "repair_steps": [
        {{"step": 1, "description": "step description", "tools_needed": ["tool1"]}},
        ...
    ],
    "estimated_cost_range": {{"min": 0, "max": 0, "currency": "GBP"}},
    "parts_needed": [
        {{"name": "part name", "approx_cost": 0, "supplier_suggestion": "where to buy"}}
    ],
    "safety_warnings": ["any safety notes"],
    "outsource_recommendation": "when/why to outsource instead of DIY"
}}"""
        }]
    )

    text = message.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    return json.loads(text)


def generate_repair_guide(equipment_make, equipment_model, fault, manual_text=None):
    """Generate a detailed step-by-step repair guide."""
    client = _get_client()

    context = f"Equipment: {equipment_make} {equipment_model}\nFault: {fault}"
    if manual_text:
        context += f"\n\nService manual excerpt:\n{manual_text[:4000]}"

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": f"""You are an experienced audio equipment repair technician. Write a detailed, beginner-friendly repair guide for this issue. The person following this guide has basic skills but limited experience.

{context}

Write the guide in clear, numbered steps. For each step, explain:
- What to do (in plain English)
- What tools are needed
- What to look out for
- Safety warnings where relevant

Include a tools/parts checklist at the top and a testing procedure at the end."""
        }]
    )

    return message.content[0].text


def draft_business_plan(inventory_summary, revenue_data=None, market_context=None):
    """Generate or update the business plan."""
    client = _get_client()

    context = f"""Business: Daniel James Audio
Location: England
Services: Studio and live sound equipment hire (backline and PA)

Inventory Summary:
{inventory_summary}"""

    if revenue_data:
        context += f"\n\nRevenue Data:\n{revenue_data}"
    if market_context:
        context += f"\n\nMarket Context:\n{market_context}"

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""Write a professional business plan for this audio hire company. Include:

1. Executive Summary
2. Business Description & Services
3. Equipment Assets
4. Target Market & Competition
5. Pricing Strategy
6. Marketing Plan
7. Financial Projections
8. Growth Strategy
9. Risk Assessment

{context}

Write in a professional but approachable tone. Use GBP for all financial figures. Format as Markdown."""
        }]
    )

    return message.content[0].text


def draft_email(template_name, context_dict):
    """Draft a professional email from a template name and context."""
    client = _get_client()

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Draft a professional email for Daniel James Audio (sound hire business in England).

Email type: {template_name}
Context: {json.dumps(context_dict, indent=2)}

Write a clear, friendly, and professional email. Sign off as Daniel James, Daniel James Audio. Use GBP for prices."""
        }]
    )

    return message.content[0].text
