import { useQuery } from '@tanstack/react-query';
import { positionService } from '../services/positionService';

export const usePositions = (pocketName: string) => {
  return useQuery({
    queryKey: ['positions', pocketName],
    queryFn: () => positionService.getPositions(pocketName),
    enabled: !!pocketName,
  });
};
