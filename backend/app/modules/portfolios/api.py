import json
import logging
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.assets.dependencies import (
    get_asset_class_repo,
    get_asset_repo,
    get_market_data_service,
)
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetClassRepository, AssetRepository
from app.modules.assets.service import MarketDataService
from app.modules.core_data.dependencies import get_current_user
from app.modules.core_data.models import User

from .analytics import PortfolioMetrics
from .dependencies import (
    get_operation_repo,
    get_portfolio_repo,
    get_portfolio_service,
    get_position_repo,
    get_transaction_service,
)
from .models import Operation, Portfolio, Position
from .repository import OperationRepository, PortfolioRepository, PositionRepository
from .schemas import (
    OperationCreate,
    OperationRead,
    PortfolioCreate,
    PortfolioDetailRead,
    PortfolioRead,
    PositionRead,
)
from .services import PortfolioService, TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _as_float(value: Any) -> float:
    return float(value)


def _portfolio_id(portfolio: Portfolio) -> int:
    return cast(int, cast(Any, portfolio.id))


def _portfolio_owner_id(portfolio: Portfolio) -> int:
    return cast(int, cast(Any, portfolio.owner_id))


def _compute_position_fields(pos: Position, portfolio: Portfolio) -> dict:
    qty = _as_float(pos.quantity)
    avg_price = _as_float(pos.average_buy_price)
    avg_fx = _as_float(pos.average_fx_rate)
    current_price = _as_float(pos.asset.current_price)
    asset_currency = pos.asset.currency

    cost_basis = qty * avg_price
    cost_basis_portfolio = cost_basis * avg_fx

    if (
        asset_currency
        and portfolio.base_currency
        and asset_currency.id == portfolio.base_currency_id
    ):
        market_value = qty * current_price
    else:
        fx = _as_float(asset_currency.exchange_rate) if asset_currency else 1.0
        market_value = qty * current_price * fx

    unrealized = market_value - cost_basis_portfolio
    return_pct = (
        unrealized / cost_basis_portfolio * 100 if cost_basis_portfolio else 0.0
    )

    return {
        "cost_basis": round(cost_basis, 3),
        "cost_basis_in_portfolio_currency": round(cost_basis_portfolio, 3),
        "market_value": round(market_value, 3),
        "unrealized_pnl": round(unrealized, 3),
        "return_pct": round(return_pct, 4),
    }


def _portfolio_computed(portfolio: Portfolio) -> dict:
    positions_value = 0.0
    total_fees = 0.0
    for pos in portfolio.positions:
        fields = _compute_position_fields(pos, portfolio)
        positions_value += fields["market_value"]
        total_fees += _as_float(pos.total_fees or 0)

    cash = _as_float(portfolio.cash_balance)
    deposited = _as_float(portfolio.total_deposited)
    total_value = cash + positions_value
    profit_loss = total_value - deposited
    return_pct = (profit_loss / deposited * 100) if deposited else 0.0

    return {
        "positions_value": round(positions_value, 3),
        "total_value": round(total_value, 3),
        "total_profit_loss": round(profit_loss, 3),
        "total_return_pct": round(return_pct, 4),
        "total_fees": round(total_fees, 2),
    }


def _serialize_portfolio(portfolio: Portfolio, detail: bool = False) -> dict:
    if detail:
        data = PortfolioDetailRead.model_validate(portfolio).model_dump()
    else:
        data = PortfolioRead.model_validate(portfolio).model_dump()

    data.update(_portfolio_computed(portfolio))

    if detail:
        positions = []
        total_value = data["total_value"]
        for pos in portfolio.positions:
            item = PositionRead.model_validate(pos).model_dump()
            item.update(_compute_position_fields(pos, portfolio))
            item["portfolio_weight_pct"] = (
                round(item["market_value"] / total_value * 100, 4)
                if total_value
                else 0.0
            )
            positions.append(item)
        data["positions"] = positions

    return data


@router.get("/", response_model=list[dict])
def list_portfolios(
    name: str | None = None,
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    user: User = Depends(get_current_user),
):
    portfolios = repo.list_by_owner(user.id, name=name)
    return [_serialize_portfolio(portfolio) for portfolio in portfolios]


@router.post("/", response_model=PortfolioRead, status_code=201)
def create_portfolio(
    data: PortfolioCreate,
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    user: User = Depends(get_current_user),
):
    if repo.get_by_owner_and_name(user.id, data.name):
        raise HTTPException(
            status_code=400, detail="Portfolio with this name already exists"
        )

    portfolio = Portfolio(
        owner_id=user.id,
        name=data.name,
        base_currency_id=data.base_currency_id,
        cash_balance=0,
        total_deposited=0,
        is_active=True,
    )
    return repo.create(portfolio)


@router.get("/positions", response_model=list[dict])
def list_positions(
    portfolio_name: str = Query(...),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    position_repo: PositionRepository = Depends(get_position_repo),
    market_data_svc: MarketDataService = Depends(get_market_data_service),
    user: User = Depends(get_current_user),
):
    portfolio = portfolio_repo.get_by_owner_and_name(user.id, portfolio_name)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        market_data_svc.update_currency_rates()
    except Exception:
        logger.exception(
            "Failed to update currency rates for portfolio %s", portfolio.id
        )

    positions = position_repo.list_by_portfolio(_portfolio_id(portfolio))
    for pos in positions:
        try:
            market_data_svc.update_asset_price(pos.asset)
        except Exception:
            logger.exception("Failed to update asset price for %s", pos.asset.ticker)

    total_value = _portfolio_computed(portfolio)["total_value"]
    result = []
    for pos in positions:
        item = PositionRead.model_validate(pos).model_dump()
        item.update(_compute_position_fields(pos, portfolio))
        item["portfolio_weight_pct"] = (
            round(item["market_value"] / total_value * 100, 4) if total_value else 0.0
        )
        result.append(item)
    return result


@router.get("/{portfolio_id}", response_model=PortfolioDetailRead)
def get_portfolio(
    portfolio_id: int,
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    user: User = Depends(get_current_user),
):
    portfolio = repo.get_by_id(portfolio_id)
    if portfolio is None or _portfolio_owner_id(portfolio) != user.id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return _serialize_portfolio(portfolio, detail=True)


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: int,
    repo: PortfolioRepository = Depends(get_portfolio_repo),
    user: User = Depends(get_current_user),
):
    portfolio = repo.get_by_id(portfolio_id)
    if portfolio is None or _portfolio_owner_id(portfolio) != user.id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    repo.delete(portfolio)


@router.get("/operations", response_model=list[OperationRead])
def list_operations(
    portfolio_name: str | None = None,
    op_repo: OperationRepository = Depends(get_operation_repo),
    user: User = Depends(get_current_user),
):
    return op_repo.list_by_owner(user.id, portfolio_name=portfolio_name)


@router.post("/operations", response_model=OperationRead, status_code=201)
def create_operation(
    data: OperationCreate,
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    asset_repo: AssetRepository = Depends(get_asset_repo),
    asset_class_repo: AssetClassRepository = Depends(get_asset_class_repo),
    op_repo: OperationRepository = Depends(get_operation_repo),
    transaction_svc: TransactionService = Depends(get_transaction_service),
    portfolio_svc: PortfolioService = Depends(get_portfolio_service),
    user: User = Depends(get_current_user),
):
    portfolio = portfolio_repo.get_by_id(data.portfolio_id)
    if portfolio is None or _portfolio_owner_id(portfolio) != user.id:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    asset = None
    if data.asset_id:
        asset = asset_repo.get_by_id(data.asset_id)
    elif data.ticker:
        ticker = data.ticker.strip().upper()
        asset = asset_repo.get_by_ticker(ticker)
        if not asset:
            if data.asset_class:
                asset_class = asset_class_repo.get_or_create(data.asset_class)
                asset = Asset(
                    ticker=ticker,
                    name=ticker,
                    asset_class_id=asset_class.id,
                    currency_id=cast(int, cast(Any, portfolio.base_currency_id)),
                )
                asset = asset_repo.create(asset)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Asset does not exist. Provide asset_class to create it.",
                )

    op_type = data.operation_type
    asset_ops = ("buy", "sell", "dividend")
    cash_ops = ("deposit", "withdrawal")

    if op_type in asset_ops and not asset:
        raise HTTPException(status_code=400, detail=f"'{op_type}' requires an asset")
    if op_type in cash_ops and asset:
        raise HTTPException(
            status_code=400, detail=f"'{op_type}' should not have an asset"
        )

    if op_type in ("buy", "sell"):
        if data.quantity <= 0 or data.price <= 0:
            raise HTTPException(
                status_code=400, detail="Quantity and price must be > 0"
            )
        if data.fee < 0:
            raise HTTPException(status_code=400, detail="Fee must be >= 0")
        if data.fx_rate <= 0:
            raise HTTPException(status_code=400, detail="FX rate must be > 0")
    elif op_type in ("deposit", "withdrawal"):
        if data.amount is None or data.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be > 0")
        if data.fee < 0:
            raise HTTPException(status_code=400, detail="Fee must be >= 0")
    elif op_type == "dividend":
        if not asset:
            raise HTTPException(status_code=400, detail="Dividend requires an asset")
        if data.amount is None or data.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be > 0")
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported operation type: {op_type}"
        )

    svc_data = {
        "portfolio": portfolio,
        "asset": asset,
        "quantity": data.quantity,
        "price": data.price,
        "amount": data.amount,
        "fee": data.fee,
        "fx_rate": data.fx_rate,
    }

    try:
        if op_type == "buy":
            transaction_svc.execute_buy(svc_data)
        elif op_type == "sell":
            transaction_svc.execute_sell(svc_data)
        elif op_type == "deposit":
            portfolio_svc.deposit_cash(svc_data)
        elif op_type == "withdrawal":
            portfolio_svc.withdraw_cash(svc_data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    operation = Operation(
        portfolio_id=_portfolio_id(portfolio),
        asset_id=cast(int, cast(Any, asset.id)) if asset else None,
        operation_type=op_type,
        quantity=data.quantity,
        price=data.price,
        amount=data.amount,
        fee=data.fee,
        fx_rate=data.fx_rate,
        notes=data.notes,
        operation_date=data.operation_date,
    )
    return op_repo.create(operation)


@router.delete("/operations/{operation_id}", status_code=204)
def delete_operation(
    operation_id: int,
    op_repo: OperationRepository = Depends(get_operation_repo),
    portfolio_svc: PortfolioService = Depends(get_portfolio_service),
    user: User = Depends(get_current_user),
):
    operation = op_repo.get_by_id(operation_id)
    if operation is None or _portfolio_owner_id(operation.portfolio) != user.id:
        raise HTTPException(status_code=404, detail="Operation not found")
    try:
        portfolio_svc.delete_operation(operation)
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/portfolio-vectors")
def portfolio_vectors(
    portfolio_name: str | None = Query(None, alias="portfolioName"),
    start_date: str | None = Query(None, alias="startDate"),
    end_date: str | None = Query(None, alias="endDate"),
    interval: str = "1d",
    vectors: str = "[]",
    op_repo: OperationRepository = Depends(get_operation_repo),
    user: User = Depends(get_current_user),
):
    operations = op_repo.list_by_owner(user.id, portfolio_name=portfolio_name)

    if not operations:
        return {}

    try:
        requested_vectors = json.loads(vectors)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid vectors payload.") from exc

    try:
        if not start_date or not end_date:
            raise ValueError("Missing date")
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        ) from exc

    metrics = PortfolioMetrics(
        operations=operations,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    result: dict = {"date": metrics.get_date_vector().tolist()}
    vector_map = {
        "assets": metrics.get_assets_vectors,
        "asset_classes": metrics.get_asset_classes_vectors,
        "net_deposits_vector": metrics.get_net_deposits_vector,
        "transaction_cost_vector": metrics.get_transaction_cost_vector,
        "profit_vector": metrics.get_profit_vector,
        "free_cash_vector": metrics.get_free_cash_vector,
        "portfolio_value_vector": metrics.get_portfolio_value_vector,
    }

    keys = requested_vectors if requested_vectors else list(vector_map.keys())
    for key in keys:
        if key not in vector_map:
            continue
        value = vector_map[key]()
        if isinstance(value, dict):
            result[key] = {name: series.tolist() for name, series in value.items()}
        else:
            result[key] = value.tolist()

    return result
