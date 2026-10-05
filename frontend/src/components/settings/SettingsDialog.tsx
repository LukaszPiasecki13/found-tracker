import { useState } from 'react';
import {
  Box,
  ButtonBase,
  Dialog,
  DialogTitle,
  IconButton,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { settingsSections } from './settingsConfig';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Fullscreen settings dialog with a section rail — the same pattern as `SettingsDialog` /
 * `SettingsRail` in waterworks-monitoring-platform. The rail is a vertical column from `sm`
 * up and a horizontal tab strip above the panel below it.
 */
export default function SettingsDialog({ open, onClose }: SettingsDialogProps) {
  const theme = useTheme();
  const isNarrow = useMediaQuery(theme.breakpoints.down('sm'));
  const [selectedKey, setSelectedKey] = useState(settingsSections[0]?.key);

  const active = settingsSections.find((s) => s.key === selectedKey) ?? settingsSections[0];
  if (!active) return null;

  return (
    <Dialog open={open} onClose={onClose} fullScreen aria-labelledby="settings-title">
      <DialogTitle
        id="settings-title"
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: 1,
          borderColor: 'divider',
          px: { xs: 2, sm: 3 },
          py: { xs: 1.5, sm: 2 },
        }}
      >
        <Typography variant="h6" component="span" sx={{ fontWeight: 600 }}>
          Ustawienia
        </Typography>
        <IconButton onClick={onClose} aria-label="Zamknij">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0, flexDirection: { xs: 'column', sm: 'row' } }}>
        <Box
          role="tablist"
          aria-orientation={isNarrow ? 'horizontal' : 'vertical'}
          sx={{
            flex: 'none',
            display: 'flex',
            flexDirection: { xs: 'row', sm: 'column' },
            gap: 0.5,
            overflowX: { xs: 'auto', sm: 'visible' },
            bgcolor: 'background.default',
            borderBottom: { xs: 1, sm: 0 },
            borderRight: { xs: 0, sm: 1 },
            borderColor: 'divider',
            width: { sm: 160 },
            p: { xs: 1, sm: 1.5 },
          }}
        >
          {settingsSections.map(({ key, label, icon: Icon }) => {
            const selected = key === active.key;
            return (
              <ButtonBase
                key={key}
                role="tab"
                aria-selected={selected}
                onClick={() => setSelectedKey(key)}
                sx={{
                  flex: 'none',
                  minHeight: 44,
                  justifyContent: 'flex-start',
                  gap: 1,
                  px: 1.5,
                  borderRadius: 1.5,
                  whiteSpace: 'nowrap',
                  fontSize: 14,
                  fontWeight: selected ? 600 : 500,
                  color: selected ? 'primary.dark' : 'text.secondary',
                  bgcolor: selected ? 'rgba(13, 155, 145, 0.1)' : 'transparent',
                  borderLeft: { sm: 2 },
                  borderBottom: { xs: 2, sm: 0 },
                  borderColor: selected ? 'primary.light' : 'transparent',
                  '&:hover': { bgcolor: selected ? undefined : 'action.hover' },
                }}
              >
                <Icon sx={{ fontSize: 18 }} />
                {label}
              </ButtonBase>
            );
          })}
        </Box>

        <Box sx={{ flex: 1, minWidth: 0, overflowY: 'auto', bgcolor: 'background.paper' }}>
          <active.Panel />
        </Box>
      </Box>
    </Dialog>
  );
}
