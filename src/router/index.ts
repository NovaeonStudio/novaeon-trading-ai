import { createRouter, createWebHistory } from 'vue-router';
import { handleHotUpdate, routes } from 'vue-router/auto-routes';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

/** NovaeonTradingAI replaces the classic trading pages; old URLs forward to their successors. */
const NOVA_REDIRECTS: Record<string, string> = {
  '/trade': '/positions',
  '/open_trades': '/positions',
  '/dashboard': '/command',
  '/graph': '/markets',
  '/logs': '/journal',
  '/trade_history': '/trades',
  '/balance': '/command',
};

router.beforeEach((to) => {
  const target = NOVA_REDIRECTS[to.path];
  if (target) return { path: target, query: to.query };
  // Init bots here...
  initBots();
  const botStore = useBotStore();
  if (!to.meta?.allowAnonymous && !botStore.hasBots) {
    // Forward to login if login is required
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    };
  } else {
    return true;
  }
});

if (import.meta.hot) {
  handleHotUpdate(router);
}

export default router;
