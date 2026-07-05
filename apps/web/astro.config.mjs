// @ts-check
import { defineConfig } from 'astro/config';
import { SITE } from '@edenscale/site-config';

// https://astro.build/config
export default defineConfig({
	site: SITE.url,
});
