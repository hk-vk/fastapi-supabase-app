from enum import Enum
import logging

logger = logging.getLogger(__name__)

class UserVerdictEnum(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"

    @classmethod
    def _missing_(cls, value):
        if not value:
            return None
            
        try:
            value = str(value).lower()
            mapping = {
                'agree': 'approved',
                'disagree': 'rejected',
            }
            value = mapping.get(value, value)
            
            for member in cls:
                if member.value.lower() == value:
                    return member
                    
            logger.warning(f"Invalid verdict value: {value}")
            return None
        except Exception as e:
            logger.error(f"Error processing verdict: {str(e)}, value: {value}")
            return None
