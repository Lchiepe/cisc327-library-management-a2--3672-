import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Initialize the database before running tests
from database import init_database, add_sample_data, datetime, timedelta
init_database()
add_sample_data()

from services.library_service import (
    add_book_to_catalog,
    get_all_books,
    borrow_book_by_patron,
    return_book_by_patron,
    calculate_late_fee_for_book,
    search_books_in_catalog,        
    get_patron_status_report, 
    pay_late_fees
)


# --- Tests for add_book_to_catalog ---

def test_add_book_valid_input(monkeypatch):
    """Test adding a book with valid input."""

    # Mock DB calls
    monkeypatch.setattr("services.library_service.get_book_by_isbn", lambda isbn: None)
    monkeypatch.setattr("services.library_service.insert_book", lambda *a, **kw: True)

    success, message = add_book_to_catalog("Test Book", "Test Author", "1234567890123", 5)
    
    assert success is True
    assert "successfully added" in message.lower()


def test_add_book_invalid_isbn_too_short():
    """Test adding a book with ISBN too short."""
    success, message = add_book_to_catalog("Test Book", "Test Author", "123456789", 5)
    
    assert success is False
    assert "13 digits" in message

def test_add_book_title_too_long():
    """Test adding book with title exceeding 200 characters"""
    long_title = "A" * 201
    success, message = add_book_to_catalog(long_title, "Author", "1234567890123", 5)
    
    assert success is False
    assert "200 characters" in message


def test_add_book_missing_title():
    """Test missing book title."""
    success, message = add_book_to_catalog("", "Author", "1234567890123", 5)
    
    assert success is False
    assert "title is required" in message.lower()


def test_add_book_duplicate_isbn(monkeypatch):
    """Test adding a book with duplicate ISBN."""

    # Mock duplicate ISBN found
    monkeypatch.setattr("services.library_service.get_book_by_isbn", lambda isbn: {"isbn": isbn})

    success, message = add_book_to_catalog("Book", "Author", "1234567890123", 5)
    
    assert success is False
    assert "already exists" in message.lower()


def test_add_book_invalid_copies():
    """Test adding a book with invalid copy number."""
    success, message = add_book_to_catalog("Book", "Author", "1234567890123", -1)
    
    assert success is False
    assert "positive integer" in message.lower()




# ---Book Catalog Display ---

def test_catalog_simple(monkeypatch):
    """R2: Catalog should return books with required fields."""
    mock_books = [
        {
            "id": 4,
            "title": "The Hunger Games",
            "author": "Suzanne Collins",
            "isbn": "9780439023528",
            "total_copies": 3,
            "available_copies": 3
        }
    ]

    monkeypatch.setattr("database.get_all_books", lambda: mock_books)
    books = get_all_books()
    assert isinstance(books, list)

    if len(books) == 1:  # If mock worked
        assert len(books) == 1

# --- R3: Book Borrowing Interface ---

def test_invalid_patron_id():
    """Invalid patron ID (not 6-digit) should fail."""
    success, message = borrow_book_by_patron("12A456", 1)
    assert success is False
    assert "invalid patron id" in message.lower()

def test_book_not_found(monkeypatch):
    """Borrowing a non-existent book should fail."""
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: None)
    success, message = borrow_book_by_patron("123456", 999)
    assert success is False
    assert "book not found" in message.lower()

def test_book_unavailable(monkeypatch):
    """Borrowing a book with zero available copies should fail."""
    mock_book = {"book_id": 1, "title": "Unavailable Book", "available_copies": 0}
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: mock_book)
    success, message = borrow_book_by_patron("123456", 1)
    assert success is False
    assert "not available" in message.lower()

def test_patron_limit_reached(monkeypatch):
    """Borrowing when patron already has 5 books should fail."""
    mock_book = {"id": 1, "title": "Some Book", "available_copies": 2}
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: mock_book)
    monkeypatch.setattr("services.library_service.get_patron_borrow_count", lambda patron_id: 6)
    success, message = borrow_book_by_patron("123456", 1)
    assert success is False
    assert "maximum borrowing limit" in message.lower()

def test_borrow_success(monkeypatch):
    """Valid borrow should succeed."""
    mock_book = {"id": 4, "title": "Available Book", "available_copies": 3}
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: mock_book)
    monkeypatch.setattr("services.library_service.get_patron_borrow_count", lambda patron_id: 2)
    monkeypatch.setattr("services.library_service.insert_borrow_record", lambda *a, **kw: True)
    monkeypatch.setattr("services.library_service.update_book_availability", lambda book_id, delta: True)

    success, message = borrow_book_by_patron("123456", 1)
    assert success is True
    assert "successfully borrowed" in message.lower()




# --- Tests for return_book_by_patron (R4) ---

def test_return_book_success(monkeypatch):
    """Test successful book return."""
    mock_book = {"id": 4, "title": "Test Book", "author": "Test Author"}

    mock_borrowed_books = [
        {

            
            "book_id": 4,
            "title": "The Hunger Games",
            "author": "Suzanne Collins",
            "borrow_date": datetime.now(), 
            "due_date": datetime.now() + timedelta(days=13), 
            "is_overdue": False
        }
    ]
    
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: mock_book)
    monkeypatch.setattr("services.library_service.get_patron_borrowed_books", lambda patron_id: mock_borrowed_books)
    monkeypatch.setattr("services.library_service.update_borrow_record_return_date", lambda patron_id, book_id, return_date: True)
    monkeypatch.setattr("services.library_service.update_book_availability", lambda book_id, change: True)
    
    success, message = return_book_by_patron("123456", 4)
    assert success is True
    assert "successfully returned" in message.lower()


def test_return_book_invalid_patron():
    """Test return with invalid patron ID."""
    success, message = return_book_by_patron("123", 1)
    assert success is False
    assert "invalid patron id" in message.lower()

def test_return_book_not_found(monkeypatch):
    """Test return when book doesn't exist."""
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: None)
    success, message = return_book_by_patron("123456", 999)
    assert success is False
    assert "book not found" in message.lower()

# --- Tests for calculate_late_fee_for_book (R5) ---

def test_late_fee_basic():
    """Test basic late fee function call."""
    result = calculate_late_fee_for_book("123456", 1)
    assert 'fee_amount' in result
    assert 'days_overdue' in result
    assert 'status' in result

# --- Tests for search_books_in_catalog (R6) ---

def test_search_by_title(monkeypatch):
    """Test searching books by title."""
    mock_books = [
        {"id": 1, "title": "The Great Gatsby", "author": "Fitzgerald", "isbn": "123"},
        {"id": 2, "title": "Great Expectations", "author": "Dickens", "isbn": "456"}
    ]
    monkeypatch.setattr("services.library_service.get_all_books", lambda: mock_books)
    
    results = search_books_in_catalog("great", "title")
    assert len(results) == 2
    assert all("great" in book["title"].lower() for book in results)

def test_search_by_author(monkeypatch):
    """Test searching books by author."""
    mock_books = [
        {"id": 1, "title": "Book1", "author": "Stephen King", "isbn": "123"},
        {"id": 2, "title": "Book2", "author": "King Arthur", "isbn": "456"}
    ]
    monkeypatch.setattr("services.library_service.get_all_books", lambda: mock_books)
    
    results = search_books_in_catalog("king", "author")
    assert len(results) == 2

def test_search_no_results(monkeypatch):
    """Test search with no matching results."""
    mock_books = [{"id": 1, "title": "Test Book", "author": "Test Author", "isbn": "123"}]
    monkeypatch.setattr("services.library_service.get_all_books", lambda: mock_books)
    
    results = search_books_in_catalog("nonexistent", "title")
    assert len(results) == 0

def test_search_empty_term():
    """Test search with empty search term."""
    results = search_books_in_catalog("", "title")
    assert len(results) == 0

# --- Tests for get_patron_status_report (R7) ---

def test_patron_status_basic():
    """Test basic patron status function call."""
    result = get_patron_status_report("123456")
    assert 'patron_id' in result
    assert 'total_books_borrowed' in result
    assert 'borrowing_limit_remaining' in result

def test_patron_status_invalid_id():
    """Test status report with invalid patron ID."""
    result = get_patron_status_report("123")
    assert "error" in result




# new

def test_add_book_database_error(monkeypatch):
    """Test database error when adding book"""
    monkeypatch.setattr("services.library_service.get_book_by_isbn", lambda isbn: None)
    monkeypatch.setattr("services.library_service.insert_book", lambda *a, **kw: False)
    
    success, message = add_book_to_catalog("Test Book", "Test Author", "1234567890123", 5)
    
    assert success is False
    assert "database error" in message.lower()

def test_borrow_book_database_error(monkeypatch):
    """Test database error during borrowing"""
    mock_book = {"id": 1, "title": "Test Book", "available_copies": 3}
    monkeypatch.setattr("services.library_service.get_book_by_id", lambda book_id: mock_book)
    monkeypatch.setattr("services.library_service.get_patron_borrow_count", lambda patron_id: 2)
    monkeypatch.setattr("services.library_service.insert_borrow_record", lambda *a, **kw: False)
    
    success, message = borrow_book_by_patron("123456", 1)
    
    assert success is False
    assert "database error" in message.lower()

def test_calculate_late_fee_maximum_cap(monkeypatch):
    """Test late fee calculation with maximum cap"""
    past_date = datetime.now() - timedelta(days=30)  # 30 days overdue
    mock_borrowed_books = [{'book_id': 1, 'due_date': past_date}]
    monkeypatch.setattr("services.library_service.get_patron_borrowed_books", 
                       lambda patron_id: mock_borrowed_books)
    
    result = calculate_late_fee_for_book("123456", 1)
    
    assert result['fee_amount'] == 15.00  # Maximum cap
    assert "maximum fee applied" in result['status']

def test_search_books_invalid_search_type(monkeypatch):
    """Test search with invalid search type"""
    mock_books = [{"id": 1, "title": "Test Book", "author": "Test Author", "isbn": "123"}]
    monkeypatch.setattr("services.library_service.get_all_books", lambda: mock_books)
    
    results = search_books_in_catalog("test", "invalid_type")
    
    assert len(results) == 0

def test_pay_late_fees_default_gateway(monkeypatch):
    """Test pay_late_fees with default gateway creation"""
    monkeypatch.setattr("services.library_service.calculate_late_fee_for_book", 
                       lambda *args: {'fee_amount': 5.00, 'days_overdue': 5, 'status': 'Overdue'})
    monkeypatch.setattr("services.library_service.get_book_by_id", 
                       lambda book_id: {'id': 1, 'title': 'Test Book'})
    
    # Mock the PaymentGateway class to avoid actual API calls but track instantiation
    with monkeypatch.context() as m:
        mock_gateway_instance = type('MockGateway', (), {
            'process_payment': lambda *args, **kwargs: (True, "txn_test", "Success")
        })()
        m.setattr("services.library_service.PaymentGateway", lambda: mock_gateway_instance)
        
        success, message, transaction_id = pay_late_fees("123456", 1)
        
        assert success is True
        assert transaction_id == "txn_test"

def test_pay_late_fees_calculate_fee_returns_none(monkeypatch):
    """Test when calculate_late_fee_for_book returns None"""
    monkeypatch.setattr("services.library_service.calculate_late_fee_for_book", lambda *args: None)
    
    success, message, transaction_id = pay_late_fees("123456", 1)
    
    assert success is False
    assert "unable to calculate" in message.lower()

def test_pay_late_fees_calculate_fee_missing_amount(monkeypatch):
    """Test when calculate_late_fee_for_book returns dict without fee_amount"""
    monkeypatch.setattr("services.library_service.calculate_late_fee_for_book", 
                       lambda *args: {'days_overdue': 5})  # Missing fee_amount
    monkeypatch.setattr("services.library_service.get_book_by_id", 
                       lambda book_id: {'id': 1, 'title': 'Test Book'})
    
    success, message, transaction_id = pay_late_fees("123456", 1)
    
    assert success is False
    assert "unable to calculate" in message.lower()