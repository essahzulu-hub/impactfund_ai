"""PayPal sandbox integration for ImpactFund AI.

Donations are created as PayPal v1 payments (sandbox) with an approval
redirect. After the donor approves, PayPal sends them back to
``payment_executed`` where the payment is executed and the campaign total is
updated with the captured amount.
"""

import os

import paypalrestsdk
from flask import flash, redirect, request, url_for

from app.auth import login_required

# Point at the PayPal sandbox REST API.
paypalrestsdk.configure(
    {
        "mode": "sandbox",
        "client_id": os.getenv("PAYPAL_CLIENT_ID", ""),
        "client_secret": os.getenv("PAYPAL_CLIENT_SECRET", ""),
    }
)

MIN_DONATION = 1.0
MAX_DONATION = 100000.0


def create_paypal_bp(app, get_db):
    """Mount the PayPal routes on the app."""

    @app.route("/campaigns/<int:campaign_id>/donate", methods=["POST"])
    @login_required
    def create_order(campaign_id):
        """Create a PayPal sandbox payment for the chosen donation amount."""
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title FROM campaigns WHERE id = %s",
                    (campaign_id,),
                )
                row = cur.fetchone()

        if not row:
            return "Campaign not found", 404

        try:
            amount = round(float(request.form.get("amount", "10")), 2)
        except (TypeError, ValueError):
            amount = 0

        if not MIN_DONATION <= amount <= MAX_DONATION:
            flash(
                f"Enter a donation between ${MIN_DONATION:,.0f} and ${MAX_DONATION:,.0f}.",
                "error",
            )
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        title = row[0]
        amount_value = f"{amount:.2f}"

        payment = paypalrestsdk.Payment(
            {
                "intent": "sale",
                "payer": {"payment_method": "paypal"},
                "redirect_urls": {
                    "return_url": url_for(
                        "payment_executed", campaign_id=campaign_id, _external=True
                    ),
                    "cancel_url": url_for(
                        "campaign_detail",
                        campaign_id=campaign_id,
                        paypal="cancel",
                        _external=True,
                    ),
                },
                "transactions": [
                    {
                        "amount": {"total": amount_value, "currency": "USD"},
                        "description": f"Support {title}"[:127],
                        "item_list": {
                            "items": [
                                {
                                    "name": title[:127],
                                    "sku": f"campaign-{campaign_id}",
                                    "quantity": 1,
                                    "price": amount_value,
                                    "currency": "USD",
                                }
                            ]
                        },
                    }
                ],
            }
        )

        if not payment.create():
            app.logger.error("PayPal payment creation failed: %s", payment.error)
            flash("PayPal could not start the donation. Please try again.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        for link in payment.links or []:
            if link.rel == "approval_url":
                return redirect(link.href)

        app.logger.error("No approval link returned by PayPal: %s", payment.to_dict())
        flash("PayPal did not return an approval page. Please try again.", "error")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    @app.get("/campaigns/<int:campaign_id>/payment-executed")
    def payment_executed(campaign_id):
        """Execute the approved PayPal payment and record the amount raised."""
        payment_id = request.args.get("paymentId", "")
        payer_id = request.args.get("PayerID", "")

        if not payment_id or not payer_id:
            flash("PayPal did not return a completed payment.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if not payment.execute({"payer_id": payer_id}):
                app.logger.error("PayPal payment execution failed: %s", payment.error)
                flash("PayPal could not complete the donation. Please try again.", "error")
                return redirect(url_for("campaign_detail", campaign_id=campaign_id))

            amount = float(payment.transactions[0].amount.total)
        except Exception:
            app.logger.exception(
                "Failed to execute PayPal payment %s for campaign %s",
                payment_id,
                campaign_id,
            )
            flash("We could not confirm the donation with PayPal.", "error")
            return redirect(url_for("campaign_detail", campaign_id=campaign_id))

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE campaigns
                       SET amount_raised = amount_raised + %s
                     WHERE id = %s
                     RETURNING amount_raised
                    """,
                    (amount, campaign_id),
                )
                row = cur.fetchone()

        if not row:
            return "Campaign not found", 404

        app.logger.info(
            "Donation of %.2f captured for campaign %s via PayPal (payment %s)",
            amount,
            campaign_id,
            payment_id,
        )

        flash(f"Thank you! Your ${amount:,.2f} donation has been recorded.", "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    return app
