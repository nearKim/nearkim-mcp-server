from __future__ import annotations


class DomainException(Exception):
    pass


class TaskNotFoundException(DomainException):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskIgnoredException(DomainException):
    def __init__(self, task_id: str, reason: str):
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Task {task_id} ignored: {reason}")


class ClassificationException(DomainException):
    pass


class InvalidQuadrantException(ClassificationException):
    def __init__(self, quadrant: str):
        self.quadrant = quadrant
        super().__init__(f"Invalid quadrant: {quadrant}")


class LLMResponseFormatError(ClassificationException):
    def __init__(self, response: str = ""):
        self.response = response
        msg = "LLM response format invalid"
        if response:
            msg += f": {response}"
        super().__init__(msg)


class LabelCreationException(DomainException):
    def __init__(self, label_name: str, reason: str = ""):
        self.label_name = label_name
        self.reason = reason
        msg = f"Cannot create label '{label_name}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class CacheNotLoadedException(DomainException):
    def __init__(self, cache_type: str):
        self.cache_type = cache_type
        super().__init__(f"{cache_type} cache not loaded")


class WebhookValidationException(DomainException):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Webhook validation failed: {reason}")