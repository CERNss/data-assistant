## ADDED Requirements

### Requirement: Logger to processor tasks use a versioned NATS contract
The logger MUST publish image tagging tasks with a versioned payload format that does not require `image_path` as the cross-service contract field.

#### Scenario: Logger publishes v2 contract payload
- **WHEN** logger publishes a tagging task to NATS
- **THEN** payload MUST include `version`, `image_id`, `sha256`, `source_url`, `original_url`, and `context`

#### Scenario: Processor consumes v2 contract payload
- **WHEN** processor receives a v2 tagging task payload
- **THEN** it MUST decode and map payload fields into processor queue items without requiring producer-side local queue APIs

### Requirement: Backward-compatible decode during migration
The processor MUST support legacy v1 payload decode during migration until cutover is complete.

#### Scenario: Processor receives legacy v1 payload
- **WHEN** payload contains legacy fields (`image_path`, `context`) and no `version`
- **THEN** decoder MUST accept the payload and normalize it into the runtime task structure used by processor

#### Scenario: Invalid payload is rejected
- **WHEN** payload misses required task identity fields after normalization
- **THEN** decoder MUST raise a validation error and the message MUST be logged and skipped

### Requirement: Shared contract package has pure schema responsibilities
The shared contract package MUST only define task schema, versioning, and encode/decode validation behavior.

#### Scenario: Contract package boundary
- **WHEN** `contracts/chat_image_task.py` is inspected
- **THEN** it MUST NOT include NATS connection logic, config loading, or filesystem I/O
