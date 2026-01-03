"""
Payment Gateway Integration (Stage 5)
Handles payment processing with Stripe
"""
import os
from typing import Optional, Dict, Any
from decimal import Decimal
import stripe
from dotenv import load_dotenv

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


class PaymentManager:
    """
    Manages payment processing with Stripe
    """
    
    def __init__(self):
        if not stripe.api_key:
            print("Warning: STRIPE_SECRET_KEY not set. Payment functionality will be disabled.")
        self.stripe_available = bool(stripe.api_key)
    
    def is_available(self) -> bool:
        """Check if Stripe is configured"""
        return self.stripe_available
    
    def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "ils",
        booking_id: str = None,
        customer_id: str = None,
        cabin_id: str = None,
        description: str = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Intent
        
        Args:
            amount: Amount in ILS (will be converted to agorot)
            currency: Currency code (default: "ils")
            booking_id: Booking UUID
            customer_id: Customer UUID
            cabin_id: Cabin ID
            description: Payment description
            metadata: Additional metadata
        
        Returns:
            Payment Intent object with client_secret
        """
        if not self.is_available():
            raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY in .env")
        
        # Convert ILS to agorot (smallest currency unit)
        amount_agorot = int(float(amount) * 100)
        
        # Build metadata
        payment_metadata = metadata or {}
        if booking_id:
            payment_metadata["booking_id"] = booking_id
        if customer_id:
            payment_metadata["customer_id"] = customer_id
        if cabin_id:
            payment_metadata["cabin_id"] = cabin_id
        
        # Create Payment Intent
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_agorot,
                currency=currency,
                description=description or f"Booking {booking_id}",
                metadata=payment_metadata,
                automatic_payment_methods={
                    "enabled": True,
                },
            )
            
            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount_agorot,
                "currency": currency,
                "status": payment_intent.status,
            }
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")
    
    def verify_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Verify Stripe webhook signature
        
        Args:
            payload: Raw request body
            signature: Stripe signature from header
        
        Returns:
            Event object if valid
        """
        if not STRIPE_WEBHOOK_SECRET:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            raise ValueError(f"Invalid payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Invalid signature: {str(e)}")
    
    def get_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Retrieve a Payment Intent by ID
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
        
        Returns:
            Payment Intent object
        """
        if not self.is_available():
            raise ValueError("Stripe is not configured")
        
        try:
            return stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")
    
    def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[Decimal] = None,
        reason: str = "requested_by_customer"
    ) -> Dict[str, Any]:
        """
        Create a refund for a payment
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            amount: Amount to refund (None = full refund)
            reason: Refund reason
        
        Returns:
            Refund object
        """
        if not self.is_available():
            raise ValueError("Stripe is not configured")
        
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
                "reason": reason,
            }
            if amount:
                refund_params["amount"] = int(float(amount) * 100)  # Convert to agorot
            
            refund = stripe.Refund.create(**refund_params)
            return {
                "refund_id": refund.id,
                "amount": refund.amount / 100,  # Convert from agorot to ILS
                "currency": refund.currency,
                "status": refund.status,
            }
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")


# Global instance
_payment_manager = None


def get_payment_manager() -> PaymentManager:
    """Get or create global PaymentManager instance"""
    global _payment_manager
    if _payment_manager is None:
        _payment_manager = PaymentManager()
    return _payment_manager

