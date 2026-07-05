// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { SITE } from '@edenscale/site-config';

// https://astro.build/config
export default defineConfig({
	site: SITE.url,
	// Served by the gateway worker under /docs (see apps/gateway).
	base: SITE.paths.docs,
	integrations: [
		starlight({
			title: `${SITE.name} Docs`,
			logo: {
				light: '@edenscale/brand/assets/mark.svg',
				dark: '@edenscale/brand/assets/mark-inverse.svg',
			},
			customCss: ['./src/styles/custom.css'],
			sidebar: [
				{
					label: 'Investors',
					items: [
						{ label: 'Overview', slug: 'investors/overview' },
						{ label: 'Portfolio & funds', slug: 'investors/portfolio' },
						{
							label: 'Capital calls & distributions',
							slug: 'investors/capital-calls-and-distributions',
						},
						{
							label: 'Documents & communications',
							slug: 'investors/documents-and-communications',
						},
						{ label: 'Account, tasks & notifications', slug: 'investors/account' },
						{ label: 'API reference', slug: 'investors/api-reference' },
					],
				},
				{
					label: 'Guides',
					items: [
						// Each item here is one entry in the navigation menu.
						{ label: 'Tasks', slug: 'guides/tasks' },
					],
				},
				{
					label: 'Reference',
					items: [{ autogenerate: { directory: 'reference' } }],
				},
			],
		}),
	],
});
