"""Harness de prueba del middleware cosmetics_design como agente Anthropic.

Replica el patron de agents/01-motor-bi-conversacional/backend/app/core/agent.py
(FastAPI + anthropic.AsyncAnthropic + tool-use loop + ServiceRegistry) para que
podamos validar de punta a punta que el middleware es consumible por un agente
de David antes de entregarlo al repo de agentes.

No es codigo de produccion. Es un harness para integration-testing.
"""
