import pytest
import sys
import os
from unittest.mock import Mock, patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules
from services.library_service import pay_late_fees, refund_late_fee_payment
from services.payment_service import PaymentGateway

# Helper functionn
def _is_success(ret):
    if isinstance(ret, tuple):
        return bool(ret[0])
    if isinstance(ret, dict):
        return bool(ret.get("success", True))
    return bool(ret)

class TestPayLateFees:
    """Test cases for pay_late_fees function"""


    def test_pay_late_fees_success(self, monkeypatch):
        """Test successful payment processing"""
        patron_id = "123456"
        book_id = 101

        # Stub database functions using monkeypatch
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 5.00, 'days_overdue': 5, 'status': 'Overdue'})
        monkeypatch.setattr('services.library_service.get_book_by_id', 
                           lambda *args, **kwargs: {'id': book_id, 'title': 'The Hunger Games'})

        # Mock payment gateway
        gateway = Mock(spec=PaymentGateway)
        gateway.process_payment.return_value = (True, "txn_abc123", "Payment processed successfully")

        success, message, transaction_id = pay_late_fees(patron_id, book_id, payment_gateway=gateway)

        # assert results
        assert success is True
        assert transaction_id == "txn_abc123"
        assert "success" in message.lower()

        # Verify mock was called correctly
        gateway.process_payment.assert_called_once_with(
            patron_id=patron_id,
            amount=5.00,
            description="Late fees for 'The Hunger Games'"
        )

    def test_pay_late_fees_declined_by_gateway(self, monkeypatch):
        """Test payment declined by gateway"""
        patron_id = "123456"
        book_id = 101
        
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 8.0, 'days_overdue': 8, 'status': 'Overdue'})
        monkeypatch.setattr('services.library_service.get_book_by_id', 
                           lambda *args, **kwargs: {'id': book_id, 'title': 'Test Book'})

        gateway = Mock(spec=PaymentGateway)
        gateway.process_payment.return_value = (False, "", "Payment declined")

        success, message, transaction_id = pay_late_fees(patron_id, book_id, payment_gateway=gateway)

        assert success is False
        assert transaction_id is None
        assert "failed" in message.lower()
        gateway.process_payment.assert_called_once()

    def test_pay_late_fees_invalid_patron_id_no_gateway_call(self, monkeypatch):
        """Test invalid patron ID doesn't call gateway"""
        invalid_patron = "12A456"
        book_id = 101
        
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 10.0, 'days_overdue': 10, 'status': 'Overdue'})
        
        gateway = Mock(spec=PaymentGateway)

        success, message, transaction_id = pay_late_fees(invalid_patron, book_id, payment_gateway=gateway)

        assert success is False
        assert "invalid patron id" in message.lower()
        assert transaction_id is None
        gateway.process_payment.assert_not_called()

    def test_pay_late_fees_zero_fee_no_gateway_call(self, monkeypatch):
        """Test zero fee doesn't call gateway"""
        patron_id = "123456"
        book_id = 101
        
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 0.0, 'days_overdue': 0, 'status': 'No fees'})
        monkeypatch.setattr('services.library_service.get_book_by_id', 
                           lambda *args, **kwargs: {'id': book_id, 'title': 'Test Book'})

        gateway = Mock(spec=PaymentGateway)

        success, message, transaction_id = pay_late_fees(patron_id, book_id, payment_gateway=gateway)

        assert success is False
        assert "no late fees" in message.lower()
        assert transaction_id is None
        gateway.process_payment.assert_not_called()

    def test_pay_late_fees_network_error_handled(self, monkeypatch):
        """Test network error exception handling"""
        patron_id = "123456"
        book_id = 101
        
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 4.50, 'days_overdue': 3, 'status': 'Overdue'})
        monkeypatch.setattr('services.library_service.get_book_by_id', 
                           lambda *args, **kwargs: {'id': book_id, 'title': 'Test Book'})

        gateway = Mock(spec=PaymentGateway)
        gateway.process_payment.side_effect = Exception("Network timeout")

        success, message, transaction_id = pay_late_fees(patron_id, book_id, payment_gateway=gateway)

        assert success is False
        assert "error" in message.lower()
        assert transaction_id is None
        gateway.process_payment.assert_called_once()

    def test_pay_late_fees_book_not_found(self, monkeypatch):
        """Test book not found scenario"""
        patron_id = "123456"
        book_id = 999
        
        monkeypatch.setattr('services.library_service.calculate_late_fee_for_book', 
                           lambda *args, **kwargs: {'fee_amount': 5.00, 'days_overdue': 5, 'status': 'Overdue'})
        monkeypatch.setattr('services.library_service.get_book_by_id', 
                           lambda *args, **kwargs: None)

        gateway = Mock(spec=PaymentGateway)

        success, message, transaction_id = pay_late_fees(patron_id, book_id, payment_gateway=gateway)

        assert success is False
        assert "book not found" in message.lower()
        assert transaction_id is None
        gateway.process_payment.assert_not_called()


class TestRefundLateFeePayment:
    """Test cases for refund_late_fee_payment function"""

    def test_refund_late_fee_payment_success(self):
        """Test successful refund"""
        txn = "txn_abc123"
        amount = 5.00

        gateway = Mock(spec=PaymentGateway)
        gateway.refund_payment.return_value = (True, "Refund processed successfully")

        success, message = refund_late_fee_payment(txn, amount, payment_gateway=gateway)

        assert success is True
        assert "success" in message.lower()
        gateway.refund_payment.assert_called_once_with(txn, amount)

    def test_refund_late_fee_payment_invalid_transaction_id(self):
        """Test invalid transaction ID"""
        invalid_tx = "invalid_txn"
        amount = 5.00
        
        gateway = Mock(spec=PaymentGateway)

        success, message = refund_late_fee_payment(invalid_tx, amount, payment_gateway=gateway)

        assert success is False
        assert "invalid transaction id" in message.lower()
        gateway.refund_payment.assert_not_called()


    @pytest.mark.parametrize("bad_amount,expected_msg", [
        (-5.0, "greater than 0"),
        (0.0, "greater than 0"), 
        (20.0, "exceeds maximum"),
        (15.01, "exceeds maximum"),
    ])
    def test_refund_late_fee_payment_invalid_amounts(self, bad_amount, expected_msg):
        """Test various invalid amounts"""
        txn = "txn_abc123"
        gateway = Mock(spec=PaymentGateway)

        success, message = refund_late_fee_payment(txn, bad_amount, payment_gateway=gateway)

        assert success is False
        assert expected_msg in message.lower()
        gateway.refund_payment.assert_not_called()

    def test_refund_late_fee_payment_gateway_failure(self):
        """Test gateway refund failure"""
        txn = "txn_abc123"
        amount = 10.00

        gateway = Mock(spec=PaymentGateway)
        gateway.refund_payment.return_value = (False, "Refund failed")

        success, message = refund_late_fee_payment(txn, amount, payment_gateway=gateway)

        assert success is False
        assert "failed" in message.lower()
        gateway.refund_payment.assert_called_once_with(txn, amount)

    def test_refund_late_fee_payment_exception_handling(self):
        """Test exception handling during refund"""
        txn = "txn_abc123"
        amount = 8.50

        gateway = Mock(spec=PaymentGateway)
        gateway.refund_payment.side_effect = Exception("Gateway error")

        success, message = refund_late_fee_payment(txn, amount, payment_gateway=gateway)

        assert success is False
        assert "error" in message.lower()
        gateway.refund_payment.assert_called_once_with(txn, amount)

    def test_refund_late_fee_payment_maximum_allowed(self):
        """Test that maximum allowed amount ($15.00) works"""
        txn = "txn_abc123"
        amount = 15.00

        gateway = Mock(spec=PaymentGateway)
        gateway.refund_payment.return_value = (True, "Refund successful")

        success, message = refund_late_fee_payment(txn, amount, payment_gateway=gateway)

        assert success is True
        gateway.refund_payment.assert_called_once_with(txn, amount)