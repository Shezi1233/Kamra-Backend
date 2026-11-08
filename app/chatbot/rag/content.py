from __future__ import annotations

from typing import Any

# Curated public website content. Database-backed services are added separately
# by the ingestion job so prices and availability always come from the main DB.
_SITE_SECTIONS: list[dict[str, str]] = [
    {
        "source": "about",
        "title": "About Kamora Tech",
        "text": (
            "Kamora Tech is a web development studio focused on websites, e-commerce, "
            "dashboards, and custom software for small and growing businesses. "
            "Tagline: Web development, done properly. "
            "Every project starts with a clear scope and a realistic plan, so clients know "
            "what they are getting before work begins. Kamora Tech cares about fast loading, "
            "mobile usability, security, clean structure, and content that is easy to maintain. "
            "When a project is done, the client gets a handover they can understand."
        ),
    },
    {
        "source": "about",
        "title": "What Kamora Tech does",
        "text": (
            "Services include business and corporate websites, e-commerce stores, management "
            "systems and portals, dashboards and internal tools, and maintenance, speed, and "
            "SEO setup. Kamora Tech also builds school systems, hospital systems, restaurant "
            "ordering sites, booking systems, inventory systems, billing/POS systems, and other "
            "custom digital products."
        ),
    },
    {
        "source": "about",
        "title": "How Kamora Tech works",
        "text": (
            "The process is: 1) Send your requirements through the contact page or order form. "
            "2) Kamora Tech reviews the scope and prepares a written proposal. 3) You approve "
            "the scope, timeline, and price. 4) Development starts with regular updates and order "
            "tracking. 5) The project is reviewed and tested. 6) Final handover is provided after "
            "final payment. "
            "Clients get a clear scope, visible progress, maintainable code, and optional ongoing "
            "maintenance support."
        ),
    },
    {
        "source": "contact",
        "title": "Contact and support",
        "text": (
            "You can contact Kamora Tech through the contact page on the website or by email at "
            "smith14580@gmail.com. Working hours are Monday to Saturday, 10:00 to 19:00 Pakistan "
            "time (PKT). Before contacting, it helps to prepare what the website or system should "
            "do, examples you like, your target launch window, and whether you need ongoing support."
        ),
    },
    {
        "source": "policies",
        "title": "Privacy policy",
        "text": (
            "Kamora Tech collects the details you provide when you create an account, place an "
            "order, or contact the site: name, email address, phone number, company, project "
            "requirements, and order information. This information is used to respond to enquiries, "
            "deliver services, provide order tracking, send project updates, and maintain your "
            "account. Personal information is not sold. "
            "The site uses a secure session cookie to keep users signed in and a cart cookie to "
            "remember selections. Account and order records are kept as long as needed to provide "
            "services and meet legal or accounting obligations. Account deletion can be requested "
            "by emailing smith14580@gmail.com."
        ),
    },
    {
        "source": "policies",
        "title": "Refund policy",
        "text": (
            "If a project is cancelled before work has started, any deposit paid is refundable "
            "minus administrative costs already incurred. Once design or development work has "
            "started, refunds are assessed against the work completed and time committed. "
            "Completed milestones are non-refundable. Digital deliverables are non-refundable after "
            "handover. If something does not match the agreed scope, Kamora Tech will fix it under "
            "the project warranty. "
            "To request a refund, email smith14580@gmail.com with your order tracking ID and the "
            "reason. Please contact Kamora Tech before raising a chargeback so the issue can be "
            "resolved directly."
        ),
    },
    {
        "source": "policies",
        "title": "Terms of service",
        "text": (
            "By using the website you agree to provide accurate account information and to use the "
            "site lawfully. You are responsible for keeping your login credentials secure. "
            "Placing an order starts a conversation about scope. Final deliverables, timelines, and "
            "pricing are confirmed in writing before work begins. Services marked Request a Quote "
            "require a tailored proposal. Payment terms are agreed per project. Any payment shown "
            "on an order is indicative until written confirmation is issued. "
            "Unless agreed otherwise, project deliverables are handed over after final payment. "
            "Kamora Tech may reference completed work in its portfolio unless the client requests "
            "otherwise. Kamora Tech is not liable for indirect losses or issues caused by "
            "third-party services outside its control."
        ),
    },
    {
        "source": "faq",
        "title": "Pricing FAQ",
        "text": (
            "Service prices are shown on each service page when a fixed price is available. "
            "Some services are marked Request a Quote because the final cost depends on scope. "
            "For custom work, the price is confirmed in a written proposal before work begins. "
            "The cart subtotal uses the prices stored in the website database. Always confirm the "
            "final price in writing before starting a project."
        ),
    },
    {
        "source": "faq",
        "title": "Orders and tracking FAQ",
        "text": (
            "To place an order, add the services you need to the cart, go to checkout, and submit "
            "your project requirements. After checkout you receive an order tracking ID. "
            "Logged-in customers can view orders in the dashboard and track order status. "
            "Order statuses include Order Placed, Order Received, Confirmed, In Progress, "
            "Review / Testing, Completed, Delivered, and Cancelled."
        ),
    },
    {
        "source": "faq",
        "title": "Cart and checkout FAQ",
        "text": (
            "The cart remembers selected services for guests and logged-in users. Guests get a "
            "secure cart cookie. Logged-in users have their cart attached to their account. "
            "You can update quantities or remove items from the cart page. Checkout asks for "
            "company details, project requirements, optional notes, and a payment method. "
            "Payment methods listed on the site include Cash on Delivery, Bank Transfer, and "
            "Card (on confirmation)."
        ),
    },
    {
        "source": "faq",
        "title": "Project timeline FAQ",
        "text": (
            "Delivery time depends on the service and scope. Each service page includes a delivery "
            "estimate when available. A business website is usually quicker than a custom management "
            "system. The exact timeline is confirmed in the written proposal before development "
            "starts. Ongoing maintenance and support plans are available on request."
        ),
    },
    {
        "source": "faq",
        "title": "Languages and communication",
        "text": (
            "Kamora Tech communicates in English, Urdu, and Roman Urdu. The website assistant can "
            "answer in the same language the visitor uses. For detailed project discussions, use "
            "the contact form or email smith14580@gmail.com."
        ),
    },
    {
        "source": "faq",
        "title": "Security and data",
        "text": (
            "Accounts use hashed passwords and secure session tokens. The website does not sell "
            "personal information. The chatbot stores chat messages in a separate chatbot database "
            "so conversations can be continued and improved. Do not share passwords, API keys, or "
            "payment card details in chat."
        ),
    },
]


def site_documents() -> list[dict[str, Any]]:
    """Return curated public website content documents."""

    return [
        {
            "source": f"site:{section['source']}",
            "title": section["title"],
            "text": section["text"],
        }
        for section in _SITE_SECTIONS
    ]
