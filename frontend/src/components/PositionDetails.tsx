import React from 'react';
import { Box, Typography } from '@mui/material';
import type { Position } from '../types/api';
import { formatMoney, formatPercent } from '../utils/formatMoney';

interface PositionDetailsProps {
  position: Position;
  currencyCode: string;
}

interface DetailProps {
  label: string;
  value: string;
  hint?: string;
}

const Detail: React.FC<DetailProps> = ({ label, value, hint }) => (
  <Box title={hint}>
    <Typography variant="caption" color="text.secondary">
      {label}
    </Typography>
    <Typography variant="body2" fontWeight="bold">
      {value}
    </Typography>
  </Box>
);

const PositionDetails: React.FC<PositionDetailsProps> = ({ position, currencyCode }) => {
  const assetCode = position.asset.currency.code;
  return (
    <Box
      display="grid"
      gridTemplateColumns="repeat(auto-fit, minmax(180px, 1fr))"
      gap={2}
    >
      <Detail
        label="Średnia cena zakupu"
        value={formatMoney(position.average_buy_price, assetCode, 'code')}
        hint="Z opłatami, w walucie waloru"
      />
      <Detail
        label="Zmiana ceny"
        value={formatPercent(position.price_change_pct)}
        hint="Zmiana ceny waloru, bez kursu"
      />
      <Detail
        label="Zysk w walucie waloru"
        value={formatMoney(position.unrealized_pnl_asset_currency, assetCode, 'code')}
      />
      <Detail
        label="Koszt"
        value={formatMoney(position.cost_basis_in_portfolio_currency, currencyCode)}
        hint="Po kursach z dnia zakupu"
      />
      <Detail
        label="Efekt ceny"
        value={formatMoney(position.price_effect, currencyCode)}
        hint="Zmiana ceny przeliczona dzisiejszym kursem"
      />
      <Detail
        label="Efekt kursu"
        value={formatMoney(position.fx_effect, currencyCode)}
        hint="Zmiana kursu względem kursu z dnia zakupu"
      />
      {position.rate_missing && (
        <Typography variant="body2" color="text.secondary" sx={{ gridColumn: '1 / -1' }}>
          Brak kursu {assetCode}/{currencyCode}: wartość i zysk w {currencyCode}{' '}
          niedostępne.
        </Typography>
      )}
    </Box>
  );
};

export default PositionDetails;
