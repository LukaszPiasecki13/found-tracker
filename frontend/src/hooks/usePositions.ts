import { useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { positionService } from '../services/positionService';
import type { Position } from '../types/api';

// The background refresh lands after the answer. The stored positions are read again
// every POLL_INTERVAL_MS until their asset prices change, at most MAX_FETCHES_PER_REFRESH
// times (a price that did not move ends the polling at the limit).
const POLL_INTERVAL_MS = 2000;
const MAX_FETCHES_PER_REFRESH = 5;

const priceSignature = (positions: Position[]): string =>
  positions.map((position) => `${position.asset_id}:${position.asset.current_price}`).join('|');

export const usePositions = (pocketName: string) => {
  const queryClient = useQueryClient();
  // Per pocket: fetches made so far by this hook, the price signature of the first
  // fetch and of the latest one. The first fetch asks for a refresh.
  const fetches = useRef(new Map<string, number>());
  const firstSignature = useRef(new Map<string, string>());
  const latestSignature = useRef(new Map<string, string>());

  return useQuery({
    queryKey: ['positions', pocketName],
    queryFn: async () => {
      const made = fetches.current.get(pocketName) ?? 0;
      if (made === 0) {
        // A failing refresh request (provider down, offline) leaves the stored values.
        await positionService.requestRefresh(pocketName).catch(() => undefined);
      }
      fetches.current.set(pocketName, made + 1);
      const positions = await positionService.getStoredPositions(pocketName);
      const signature = priceSignature(positions);
      if (made === 0) firstSignature.current.set(pocketName, signature);
      latestSignature.current.set(pocketName, signature);
      if (made > 0) {
        // The chart's last day reads the same stored prices: refetch it after a poll.
        void queryClient.invalidateQueries({ queryKey: ['pocket-vectors'] });
      }
      return positions;
    },
    enabled: !!pocketName,
    refetchInterval: () => {
      const made = fetches.current.get(pocketName) ?? 0;
      const priceChanged =
        latestSignature.current.get(pocketName) !== firstSignature.current.get(pocketName);
      return made > 0 && made < MAX_FETCHES_PER_REFRESH && !priceChanged
        ? POLL_INTERVAL_MS
        : false;
    },
  });
};
