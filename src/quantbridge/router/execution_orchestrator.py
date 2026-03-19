from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from quantbridge.execution.order_manager import OrderLifecycleResult
from quantbridge.router.execution_plan_builder import ExecutionPlanBuilder, TradeRequest
from quantbridge.router.account_selector import AccountRuntimeStatus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AccountExecutionResult:
    account_id: str
    attempted: bool
    success: bool
    status: str
    role: str
    message: str = ""
    error: str | None = None
    trade_id: str | None = None
    order_id: str | None = None
    filled_units: float | None = None
    risk_decision: dict | None = None


@dataclass(frozen=True)
class AggregateExecutionResult:
    routing_mode: str
    overall_success: bool
    any_success: bool
    all_success: bool
    results: list[AccountExecutionResult] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=_utc_now_iso)


class MultiAccountExecutionOrchestrator:
    """Execute one trade intent across accounts based on execution policy."""

    def __init__(
        self,
        plan_builder: ExecutionPlanBuilder,
        order_manager_factory: Callable[[str], object],
    ) -> None:
        self.plan_builder = plan_builder
        self.order_manager_factory = order_manager_factory

    def _to_result(self, account_id: str, role: str, lifecycle: OrderLifecycleResult) -> AccountExecutionResult:
        return AccountExecutionResult(
            account_id=account_id,
            attempted=True,
            success=bool(lifecycle.success),
            status=str(lifecycle.status),
            role=role,
            message=lifecycle.message,
            error=lifecycle.error,
            trade_id=lifecycle.trade_id,
            order_id=lifecycle.order_id,
            filled_units=lifecycle.filled_units,
            risk_decision=lifecycle.risk_decision,
        )

    def execute(
        self,
        *,
        request: TradeRequest,
        policies: list,
        unhealthy_account_ids: list[str] | None = None,
        runtime_status_by_account: dict[str, AccountRuntimeStatus] | None = None,
    ) -> AggregateExecutionResult:
        plan = self.plan_builder.build(
            request=request,
            policies=policies,
            unhealthy_account_ids=unhealthy_account_ids,
            runtime_status_by_account=runtime_status_by_account,
        )

        results: list[AccountExecutionResult] = []
        if not plan.items:
            return AggregateExecutionResult(
                routing_mode=plan.routing_mode,
                overall_success=False,
                any_success=False,
                all_success=False,
                results=[],
                skipped=plan.skipped,
            )

        if plan.routing_mode == "single":
            item = plan.items[0]
            manager = self.order_manager_factory(item.account_id)
            lifecycle = manager.place_and_validate(
                instrument=request.instrument,
                direction=request.direction,
                units=item.planned_units,
                sl=request.sl,
                tp=request.tp,
                comment=request.comment,
                client_order_ref=request.client_order_ref,
                enforce_protection=(request.sl is not None or request.tp is not None),
            )
            results.append(self._to_result(item.account_id, item.role, lifecycle))

        elif plan.routing_mode == "primary_backup":
            success_seen = False
            for item in plan.items:
                if success_seen:
                    results.append(
                        AccountExecutionResult(
                            account_id=item.account_id,
                            attempted=False,
                            success=False,
                            status="not_attempted_after_success",
                            role=item.role,
                            message="previous_account_succeeded",
                        )
                    )
                    continue
                manager = self.order_manager_factory(item.account_id)
                lifecycle = manager.place_and_validate(
                    instrument=request.instrument,
                    direction=request.direction,
                    units=item.planned_units,
                    sl=request.sl,
                    tp=request.tp,
                    comment=request.comment,
                    client_order_ref=request.client_order_ref,
                    enforce_protection=(request.sl is not None or request.tp is not None),
                )
                result = self._to_result(item.account_id, item.role, lifecycle)
                results.append(result)
                if result.success:
                    success_seen = True

        else:  # fanout
            for item in plan.items:
                manager = self.order_manager_factory(item.account_id)
                lifecycle = manager.place_and_validate(
                    instrument=request.instrument,
                    direction=request.direction,
                    units=item.planned_units,
                    sl=request.sl,
                    tp=request.tp,
                    comment=request.comment,
                    client_order_ref=request.client_order_ref,
                    enforce_protection=(request.sl is not None or request.tp is not None),
                )
                results.append(self._to_result(item.account_id, item.role, lifecycle))

        any_success = any(result.success for result in results)
        attempted_results = [result for result in results if result.attempted]
        all_success = bool(attempted_results) and all(result.success for result in attempted_results)
        overall_success = any_success if plan.routing_mode in {"primary_backup", "single"} else all_success

        return AggregateExecutionResult(
            routing_mode=plan.routing_mode,
            overall_success=overall_success,
            any_success=any_success,
            all_success=all_success,
            results=results,
            skipped=plan.skipped,
        )

