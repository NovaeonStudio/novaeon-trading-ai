import type { FTWsMessage } from '@/types/wsMessageTypes';
import { FtWsMessageTypes } from '@/types/wsMessageTypes';
import { t } from '@/i18n';

export function showNotification(msg: FTWsMessage, botname: string) {
  const settingsStore = useSettingsStore();
  if (settingsStore.notifications && settingsStore.notifications[msg.type]) {
    switch (msg.type) {
      case FtWsMessageTypes.entryFill:
        console.log('entryFill', msg);
        showAlert(
          t('toasts.entryFill', {
            pair: msg.pair,
            direction: msg.direction,
            rate: String(msg.open_rate),
          }),
          'success',
          botname,
        );
        break;
      case FtWsMessageTypes.exitFill:
        console.log('exitFill', msg);
        showAlert(
          t('toasts.exitFill', {
            pair: msg.pair,
            direction: msg.direction,
            rate: String(msg.open_rate),
          }),
          'success',
          botname,
        );
        break;
      case FtWsMessageTypes.exitCancel:
        console.log('exitCancel', msg);
        showAlert(
          t('toasts.exitCancel', { pair: msg.pair, reason: msg.reason }),
          'warning',
          botname,
        );
        break;
      case FtWsMessageTypes.entryCancel:
        console.log('entryCancel', msg);
        showAlert(
          t('toasts.entryCancel', { pair: msg.pair, reason: msg.reason }),
          'warning',
          botname,
        );
        break;
    }
  } else {
    console.log(`${botname}: Message ${msg.type} not shown.`);
  }
}
