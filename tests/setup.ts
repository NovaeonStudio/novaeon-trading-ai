// Unit and component tests run in English, whatever the machine's language is.
import { config } from '@vue/test-utils';
import { i18n } from '@/i18n';

i18n.global.locale.value = 'en';
config.global.plugins.push(i18n);
