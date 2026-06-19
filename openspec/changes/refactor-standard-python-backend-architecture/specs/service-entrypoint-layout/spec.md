## ADDED Requirements

### Requirement: Per-service entrypoint modules
The repository MUST provide canonical Python module entrypoints for logger and processor services under dedicated service folders.

#### Scenario: Logger service module entrypoint exists
- **WHEN** a developer starts the logger service using `python -m services.data_logger.main`
- **THEN** the logger runtime MUST start successfully via the NapCat-based logger bootstrap path

#### Scenario: Processor service module entrypoint exists
- **WHEN** a developer starts the processor service using `python -m services.data_processor.main`
- **THEN** the processor runtime MUST start successfully via the tagger worker bootstrap path

### Requirement: Legacy root entry scripts remain compatible
Legacy root entry scripts MUST remain executable and delegate to canonical service module entrypoints.

#### Scenario: data_logger_service compatibility wrapper
- **WHEN** `python data_logger_service.py` is executed
- **THEN** it MUST forward execution to the logger service module entrypoint without NoneBot runtime dependency

#### Scenario: data_processor_service compatibility wrapper
- **WHEN** `python data_processor_service.py` is executed
- **THEN** it MUST forward execution to the processor service module entrypoint
