# Base messaging adapter interface
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class MessagingAdapter(ABC):
    """
    Base interface for messaging adapters (Email, SMS).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.
        
        Args:
            config: Dictionary containing provider-specific configuration
        """
        self.config = config
        self.test_mode = config.get('test_mode', False)
    
    @abstractmethod
    def send(
        self,
        to: str,
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message.
        
        Args:
            to: Recipient (email address or phone number)
            message: Message content
            subject: Subject line (for email)
            metadata: Additional metadata
        
        Returns:
            Dictionary with:
            - status: success/failed
            - provider_reference: Provider's message ID
            - message: Status message
        """
        pass
    
    @abstractmethod
    def send_bulk(
        self,
        recipients: List[str],
        message: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send bulk messages.
        
        Args:
            recipients: List of recipients
            message: Message content
            subject: Subject line (for email)
            metadata: Additional metadata
        
        Returns:
            Dictionary with results for each recipient
        """
        pass
    
    @abstractmethod
    def get_status(
        self,
        provider_reference: str
    ) -> Dict[str, Any]:
        """
        Get message delivery status.
        
        Args:
            provider_reference: Provider's message ID
        
        Returns:
            Dictionary with delivery status
        """
        pass








