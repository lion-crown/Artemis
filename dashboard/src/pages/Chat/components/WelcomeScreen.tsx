import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ARTEMIS_LOGO_SRC } from "../../../assets/mascot";
import { useWelcomeQuickCardsLayout } from "../hooks/useWelcomeQuickCardsLayout";
import WelcomeQuickCards, { WelcomeQuickCardProbe } from "./WelcomeQuickCards";
import styles from "../index.module.less";

export interface WelcomeQuickCard {
  title: string;
  description: string;
  prompt: string;
  color: string;
  icon_name?: string | null;
}

interface WelcomeScreenProps {
  onPromptClick: (text: string) => void;
  agentName?: string | null;
  welcomeSuffix?: string | null;
  quickCards: WelcomeQuickCard[];
  hideMascot?: boolean;
}

export default function WelcomeScreen({
  onPromptClick,
  agentName,
  welcomeSuffix,
  quickCards,
  hideMascot = false,
}: WelcomeScreenProps) {
  const { t } = useTranslation();
  const [animationKey, setAnimationKey] = useState(0);
  const {
    welcomeRef,
    headingRef,
    sectionTitleRef,
    probeRef,
    expanded,
    setExpanded,
    cards,
    showToggle,
    autoHideMascot,
  } = useWelcomeQuickCardsLayout(quickCards);

  const handleMascotClick = () => {
    setAnimationKey((value) => value + 1);
  };

  const showMascot = !hideMascot && !autoHideMascot;

  return (
    <div className={styles.welcome} ref={welcomeRef}>
      <div className={styles.welcomeInner}>
        <div className={styles.welcomeHeading} ref={headingRef}>
          {showMascot && (
            <img
              key={animationKey}
              className={styles.welcomeMascot}
              src={ARTEMIS_LOGO_SRC}
              alt=""
              draggable={false}
              onClick={handleMascotClick}
              role="button"
              tabIndex={0}
              title={t("chatWelcome.mascotSwitchHint")}
              aria-label="Artemis logo"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleMascotClick();
                }
              }}
            />
          )}
          <h1 className={styles.welcomeTitle}>{t("chatWelcome.greeting")}</h1>
          <p className={styles.welcomeSubtitle}>
            {agentName ? (
              <>
                <span className={styles.welcomeAgentMention}>@{agentName}</span>
                <span className={styles.welcomeSubtitleText}>
                  {welcomeSuffix ?? t("chatWelcome.descriptionWithAgentSuffix")}
                </span>
              </>
            ) : (
              t("chatWelcome.description")
            )}
          </p>
        </div>

        {quickCards.length > 0 && (
          <WelcomeQuickCards
            cards={cards}
            showToggle={showToggle}
            expanded={expanded}
            onToggle={() => setExpanded((prev) => !prev)}
            onPromptClick={onPromptClick}
            sectionTitleRef={sectionTitleRef}
          />
        )}
      </div>

      {quickCards.length > 0 && <WelcomeQuickCardProbe probeRef={probeRef} />}
    </div>
  );
}
