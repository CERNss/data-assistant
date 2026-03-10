## 1. Service Module Layout

- [x] 1.1 Create `services/data_logger` with canonical logger entrypoint module
- [x] 1.2 Create `services/data_processor` with canonical processor entrypoint module
- [x] 1.3 Add `services/__init__.py` and per-service `__init__.py` exports

## 2. Compatibility and Runtime Wiring

- [x] 2.1 Update `napcat_logger_service.py` to delegate to `services.data_logger.main`
- [x] 2.2 Update `data_logger_service.py` compatibility wrapper to delegate to service module
- [x] 2.3 Update `data_processor_service.py` compatibility wrapper to delegate to service module
- [x] 2.4 Keep `bot.py` as compatibility wrapper delegating to logger service module

## 3. Container Build Layout

- [x] 3.1 Add `services/data_logger/Dockerfile`
- [x] 3.2 Add `services/data_processor/Dockerfile`
- [x] 3.3 Remove root `Dockerfile.logger` and `Dockerfile.processor`
- [x] 3.4 Update `docker-compose.yml` to use service-scoped Dockerfile paths

## 4. Tooling and Documentation

- [x] 4.1 Update `pyproject.toml` script entrypoints to service module paths
- [x] 4.2 Update `README.md` run instructions to `python -m services...`
- [x] 4.3 Update `AGENTS.md` run instructions and context to service layout

## 5. Verification

- [x] 5.1 Run `python3 -m compileall . -q`
- [x] 5.2 Run `python3 -m unittest discover -s tests -p 'test_*.py'`
- [x] 5.3 Run `docker compose config --quiet`
