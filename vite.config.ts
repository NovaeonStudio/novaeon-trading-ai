import { defineConfig } from 'vitest/config';

import createVuePlugin from '@vitejs/plugin-vue';
import ui from '@nuxt/ui/vite';
import { execSync } from 'child_process';
import { resolve } from 'path';
import IconsResolve from 'unplugin-icons/resolver';
import Icons from 'unplugin-icons/vite';
import VueRouter from 'vue-router/vite';

let commitHash: string = 'unknown';
try {
  commitHash = execSync('git rev-parse --short HEAD').toString();
} catch (error) {
  console.error('Failed to get commit hash. Running in this mode will not be supported.');
}

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __COMMIT_HASH__: JSON.stringify(commitHash),
    // vue-i18n: composition API only, no devtools hooks in production.
    __VUE_I18N_FULL_INSTALL__: true,
    __VUE_I18N_LEGACY_API__: false,
    __INTLIFY_PROD_DEVTOOLS__: false,
  },
  plugins: [
    // Must be registered before the Vue plugin so it can transform route blocks.
    VueRouter({
      routesFolder: 'src/pages',
      dts: 'src/typed-router.d.ts',
    }),
    createVuePlugin({
      script: {
        defineModel: true,
      },
    }),
    ui({
      ui: {
        colors: {
          primary: 'brand',
          // @ts-expect-error custom palette (defined in src/styles/tailwind.css); Nuxt UI only types the stock Tailwind greys
          neutral: 'midnight',
        },
        alert: {
          defaultVariants: {
            variant: 'subtle',
          },
        },
        button: {
          defaultVariants: {
            variant: 'subtle',
          },
        },
        table: {
          slots: {
            td: 'px-2 py-2 text-default text-sm text-left',
            th: 'px-2 py-2 text-default text-sm',
          },
        },
        tabs: {
          variants: {
            variant: {
              link: {
                trigger: 'grow focus:outline-none',
              },
            },
          },
        },
      },
      autoImport: {
        imports: ['vue', 'vue-router', '@vueuse/core', 'pinia', 'vue-i18n'],
        dts: 'src/auto-imports.d.ts',
        dirs: ['src/composables', 'src/stores', 'src/utils/**'],
        vueTemplate: true,
      },
      components: {
        resolvers: [IconsResolve()],
        dts: 'src/components.d.ts',
      },
    }),
    Icons({
      compiler: 'vue3',
    }),
  ],
  resolve: {
    dedupe: ['vue'],
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 700, // Default is 500
    sourcemap: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
    host: '127.0.0.1',
    port: 3000,
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/e2e/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*',
    ],
  },
});
