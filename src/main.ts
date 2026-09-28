import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import ui from '@nuxt/ui/vue-plugin';

import App from './App.vue';
import { VueDraggableGrid } from './plugins/vue-grid-layout';
import router from './router';
import './styles/tailwind.css';
import { detectLocale, i18n, isAppLocale, setLocale } from './i18n';

const myApp = createApp(App);

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);
myApp.use(pinia);

myApp.use(ui);
myApp.use(i18n);

myApp.use(router);
myApp.use(VueDraggableGrid);

// Load the saved (or browser) language before the first render, so German and Romanian users never see English flash.
const savedLanguage = useSettingsStore(pinia).language;
setLocale(isAppLocale(savedLanguage) ? savedLanguage : detectLocale())
  .catch(() => undefined)
  .finally(() => myApp.mount('#app'));

// Installable app (PWA): register the service worker on secure origins only.
if ('serviceWorker' in navigator && window.isSecureContext && import.meta.env.PROD) {
  navigator.serviceWorker.register('/sw.js').catch(() => undefined);
}
