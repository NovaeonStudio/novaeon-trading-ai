import type { AlertSeverity } from '@/types/alertTypes';
import { t } from '@/i18n';

export function showAlert(message: string, severity: AlertSeverity = 'warning', bot: string = '') {
  const alertStore = useAlertsStore();

  alertStore.addAlert({
    message,
    title: bot ? t('toasts.botTitle', { bot }) : t('toasts.notification'),
    severity,
    timeout: 5000,
  });
}

export function useAlertForBot(botName: string) {
  return {
    showAlert: (message: string, severity: AlertSeverity = 'warning') => {
      showAlert(message, severity, botName);
    },
  };
}

export type ShowAlertType = typeof showAlert;
