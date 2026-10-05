import type { SvgIconComponent } from '@mui/icons-material';
import { AccountCircle as AccountIcon } from '@mui/icons-material';
import type { ComponentType } from 'react';
import AccountPanel from './AccountPanel';

export interface SettingsSection {
  key: string;
  label: string;
  icon: SvgIconComponent;
  Panel: ComponentType;
}

/** Settings sections shown in the rail; add a new section here and it appears in the dialog. */
export const settingsSections: SettingsSection[] = [
  { key: 'account', label: 'Moje konto', icon: AccountIcon, Panel: AccountPanel },
];
