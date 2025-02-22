import logging

class IncludeExpectedMessagesFilter(logging.Filter):
    def filter(self, record):
        expected_messages = ["Logged In", "Logged Out", "Submitted By", "Deleted By", "Edited By"]
        for message in expected_messages:
            if message in record.msg:
                return True 
        return False
    
def create_logger():
    """Create a logger for use in all cases."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%d/%b/%Y %H:%M:%S",
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="%d/%b/%Y %H:%M:%S")
    file_handler = logging.FileHandler('app.log')
    file_handler.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    file_handler.addFilter(IncludeExpectedMessagesFilter())
    
    return logger