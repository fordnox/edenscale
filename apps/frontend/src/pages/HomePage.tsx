import { Helmet } from "react-helmet-async";
import { config } from "@/lib/config";
import { SectionHero } from "@/components/sections/section-hero.tsx";

export default function HomePage() {
  return (
    <>
      <Helmet>
        <title>{`${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <SectionHero />
    </>
  );
}
