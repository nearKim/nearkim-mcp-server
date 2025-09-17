# Error Handling and User Feedback

## How Error Details Are Exposed to Users

### 1. Successful Classification
```json
{
  "status": "applied",
  "task_id": "123456",
  "event": "item:added",
  "decision": {
    "quadrant": "Q1",
    "urgent": true,
    "important": true,
    "reason": "Task has high impact deadline tomorrow"
  },
  "error_detail": null
}
```

### 2. Fallback with Error Details
When the AI fails to classify properly, users see:

```json
{
  "status": "fallback",
  "task_id": "123456", 
  "event": "item:added",
  "decision": {
    "quadrant": "Q4",
    "urgent": false,
    "important": false,
    "reason": "Unable to classify task. Applied default priority."
  },
  "error_detail": "LLMResponseFormatError: OpenAI returned invalid JSON: Expecting property name enclosed in double quotes"
}
```

### 3. Common Error Scenarios

#### AI Response Format Error
```json
{
  "status": "fallback",
  "error_detail": "LLMResponseFormatError: AI response missing required 'quadrant' field"
}
```

#### AI Service Timeout
```json
{
  "status": "fallback",
  "error_detail": "ClassificationException: OpenAI API timeout after 30 seconds"
}
```

#### Rate Limiting
```json
{
  "status": "fallback",
  "error_detail": "ClassificationException: OpenAI API rate limit exceeded. Please try again in 60 seconds"
}
```

## Benefits of This Approach

1. **Transparency**: Users know exactly why classification failed
2. **Actionable**: Error messages guide users on what to do (retry, wait, fix format)
3. **Graceful Degradation**: Task still gets a default priority (Q4) so workflow continues
4. **Debugging**: Detailed errors help diagnose issues without checking logs

## Implementation Details

The error handling flow:

```
User Request
    ↓
Classification Pipeline
    ↓
Try Classification
    ↓
[Success] → Return Decision
    ↓
[Failure] → FallbackMiddleware catches exception
    ↓
Create fallback decision with error details
    ↓
Return to user with full context
```

## User Experience

Users can:
- See when AI classification failed vs succeeded
- Understand the specific reason for failure
- Decide whether to retry or accept the default
- Report specific errors to support with context