import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.assets.dependencies import (
    get_asset_class_repo,
    get_asset_repo,
    get_market_data_service,
)
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetClassRepository, AssetRepository
from app.modules.assets.service import MarketDataService
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

from .analytics import PocketMetrics
from .dependencies import (
    get_operation_repo,
    get_pocket_repo,
    get_portfolio_service,
    get_position_repo,
    get_transaction_service,
)
from .models import Operation, Pocket, Position
from .repository import OperationRepository, PocketRepository, PositionRepository
from .schemas import (
    OperationCreate,
    OperationRead,
    PocketCreate,
    PocketRead,
    PositionRead,
)
from .services import PortfolioService, TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


# --------------- helpers ---------------


def _compute_position_fields(pos: Position, pocket: Pocket) -> dict:
    """Compute derived fields for a Position (mirrors Django @property)."""
    qty = float(pos.quantity)
    avg_price = float(pos.average_buy_price)
    avg_fx = float(pos.average_fx_rate)
    current_price = float(pos.asset.current_price)
    asset_currency = pos.asset.currency

    cost_basis = qty * avg_price
    cost_basis_pocket = cost_basis * avg_fx

    if (
        asset_currency
        and pocket.base_currency
        and asset_currency.id == pocket.base_currency_id
    ):
        market_value = qty * current_price
    else:
        fx = float(asset_currency.exchange_rate) if asset_currency else 1.0
        market_value = qty * current_price * fx

    unrealized = market_value - cost_basis_pocket
    return_pct = (unrealized / cost_basis_pocket * 100) if cost_basis_pocket else 0.0

    return {
        "cost_basis": round(cost_basis, 3),
        "cost_basis_in_pocket_currency": round(cost_basis_pocket, 3),
        "market_value": round(market_value, 3),
        "unrealized_pnl": round(unrealized, 3),
        "return_pct": round(return_pct, 4),
    }


def _pocket_computed(pocket: Pocket) -> dict:
    positions_value = 0.0
    for pos in pocket.positions:
        fields = _compute_position_fields(pos, pocket)
        positions_value += fields["market_value"]
    cash = float(pocket.cash_balance)
    deposited = float(pocket.total_deposited)
    total_value = cash + positions_value
    pnl = total_value - deposited
    ret = (pnl / deposited * 100) if deposited else 0.0
    return {
        "positions_value": round(positions_value, 3),
        "total_value": round(total_value, 3),
        "total_profit_loss": round(pnl, 3),
        "total_return_pct": round(ret, 4),
    }


def _serialize_pocket(pocket: Pocket, detail: bool = False) -> dict:
    data = PocketRead.model_validate(pocket).model_dump()
    data.update(_pocket_computed(pocket))
    if detail:
        total_fees = sum(float(op.fee) for op in pocket.operations)
        pos_list = []
        for pos in pocket.positions:
            p = PositionRead.model_validate(pos).model_dump()
            p.update(_compute_position_fields(pos, pocket))
            # weight
            tv = data["total_value"]
            p["pocket_weight_pct"] = (
                round(p["market_value"] / tv * 100, 4) if tv else 0.0
            )
            pos_list.append(p)
        data["positions"] = pos_list
        data["total_fees"] = round(total_fees, 2)
        data["updated_at"] = (
            pocket.updated_at.isoformat() if pocket.updated_at else None
        )
    return data


# --------------- Pockets ---------------


@router.get("/pockets", response_model=list[dict])
def list_pockets(
    name: str | None = None,
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    user: User = Depends(get_current_user),
):
    pockets = pocket_repo.list_by_owner(user.id, name=name)
    return [_serialize_pocket(p) for p in pockets]


@router.post("/pockets", status_code=201)
def create_pocket(
    data: PocketCreate,
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    user: User = Depends(get_current_user),
):
    if pocket_repo.get_by_owner_and_name(user.id, data.name):
        raise HTTPException(
            status_code=400, detail="Pocket with this name already exists"
        )
    pocket = Pocket(
        owner_id=user.id, name=data.name, base_currency_id=data.base_currency_id
    )
    pocket = pocket_repo.create(pocket)
    return _serialize_pocket(pocket)


@router.get("/pockets/{pocket_id}")
def get_pocket(
    pocket_id: int,
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    user: User = Depends(get_current_user),
):
    pocket = pocket_repo.get_by_id(pocket_id)
    if not pocket or pocket.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Pocket not found")
    return _serialize_pocket(pocket, detail=True)


@router.delete("/pockets/{pocket_id}", status_code=204)
def delete_pocket(
    pocket_id: int,
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    user: User = Depends(get_current_user),
):
    pocket = pocket_repo.get_by_id(pocket_id)
    if not pocket or pocket.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Pocket not found")
    pocket_repo.delete(pocket)


# --------------- Positions ---------------


@router.get("/positions", response_model=list[dict])
def list_positions(
    pocket_name: str = Query(...),
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    position_repo: PositionRepository = Depends(get_position_repo),
    market_data_svc: MarketDataService = Depends(get_market_data_service),
    user: User = Depends(get_current_user),
):
    pocket = pocket_repo.get_by_owner_and_name(user.id, pocket_name)
    if not pocket:
        raise HTTPException(status_code=404, detail="Pocket not found")

    try:
        market_data_svc.update_currency_rates(
            base_currency_code=pocket.base_currency.code
        )
    except Exception:
        logger.exception("Failed to update currency rates for pocket %s", pocket.id)

    positions = position_repo.list_by_pocket(pocket.id)
    for pos in positions:
        try:
            market_data_svc.update_asset_price(pos.asset)
        except Exception:
            logger.exception("Failed to update asset price for %s", pos.asset.ticker)

    result = []
    for pos in positions:
        p = PositionRead.model_validate(pos).model_dump()
        p.update(_compute_position_fields(pos, pocket))
        tv = _pocket_computed(pocket)["total_value"]
        p["pocket_weight_pct"] = round(p["market_value"] / tv * 100, 4) if tv else 0.0
        result.append(p)
    return result


# --------------- Operations ---------------


@router.get("/operations", response_model=list[OperationRead])
def list_operations(
    pocket_name: str | None = None,
    op_repo: OperationRepository = Depends(get_operation_repo),
    user: User = Depends(get_current_user),
):
    return op_repo.list_by_owner(user.id, pocket_name=pocket_name)


@router.post("/operations", response_model=OperationRead, status_code=201)
def create_operation(
    data: OperationCreate,
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    asset_repo: AssetRepository = Depends(get_asset_repo),
    asset_class_repo: AssetClassRepository = Depends(get_asset_class_repo),
    op_repo: OperationRepository = Depends(get_operation_repo),
    transaction_svc: TransactionService = Depends(get_transaction_service),
    portfolio_svc: PortfolioService = Depends(get_portfolio_service),
    user: User = Depends(get_current_user),
):
    pocket = pocket_repo.get_by_id(data.pocket_id)
    if not pocket or pocket.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Pocket not found")

    asset = None
    if data.asset_id:
        asset = asset_repo.get_by_id(data.asset_id)
    elif data.ticker:
        ticker = data.ticker.strip().upper()
        asset = asset_repo.get_by_ticker(ticker)
        if not asset:
            if data.asset_class:
                ac = asset_class_repo.get_or_create(data.asset_class)
                asset = Asset(
                    ticker=ticker,
                    name=ticker,
                    asset_class_id=ac.id,
                    currency_id=pocket.base_currency_id,
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

    # Validate fields
    if op_type in ("buy", "sell"):
        if data.quantity <= 0 or data.price <= 0:
            raise HTTPException(
                status_code=400, detail="Quantity and price must be > 0"
            )
        if data.fee < 0:
            raise HTTPException(status_code=400, detail="Fee must be >= 0")
        if data.fx_rate <= 0:
            raise HTTPException(status_code=400, detail="FX rate must be > 0")
    elif op_type in cash_ops:
        if not data.amount or data.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be > 0")
        if data.fee < 0:
            raise HTTPException(status_code=400, detail="Fee must be >= 0")

    # Execute via services
    svc_data = {
        "pocket": pocket,
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
    except (ValueError, NotImplementedError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    operation = Operation(
        pocket_id=pocket.id,
        asset_id=asset.id if asset else None,
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
    if not operation or operation.pocket.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Operation not found")
    try:
        portfolio_svc.delete_operation(operation)
    except (ValueError, NotImplementedError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --------------- Pocket Vectors (Analytics) ---------------


@router.get("/pocket-vectors")
def pocket_vectors(
    pocket_name: str | None = Query(None, alias="pocketName"),
    start_date: str | None = Query(None, alias="startDate"),
    end_date: str | None = Query(None, alias="endDate"),
    interval: str = "1d",
    vectors: str = "[]",
    op_repo: OperationRepository = Depends(get_operation_repo),
    user: User = Depends(get_current_user),
):
    operations = op_repo.list_by_owner(user.id, pocket_name=pocket_name)

    if not operations:
        return {}

    requested_vectors = json.loads(vectors)

    try:
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
        end_time = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError) as err:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        ) from err

    metrics = PocketMetrics(
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        operations=operations,
    )

    result: dict = {"date": metrics.get_date_vector().tolist()}

    vector_map = {
        "assets": metrics.get_assets_vectors,
        "asset_classes": metrics.get_asset_classes_vectors,
        "net_deposits_vector": metrics.get_net_deposits_vector,
        "transaction_cost_vector": metrics.get_transaction_cost_vector,
        "profit_vector": metrics.get_profit_vector,
        "free_cash_vector": metrics.get_free_cash_vector,
        "pocket_value_vector": metrics.get_pocket_value_vector,
    }

    keys = requested_vectors if requested_vectors else list(vector_map.keys())
    for key in keys:
        if key in vector_map:
            val = vector_map[key]()
            if isinstance(val, dict):
                result[key] = {k: v.tolist() for k, v in val.items()}
            else:
                result[key] = val.tolist()

    return result
