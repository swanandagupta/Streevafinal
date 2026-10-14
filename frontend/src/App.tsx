import React, { useState, useEffect } from 'react';
import { useStreeva } from './context/StreevaContext';
import { SplashScreen } from './screens/SplashScreen';
import { OnboardingScreen } from './screens/OnboardingScreen';
import { AuthScreen } from './screens/AuthScreen';
import { HomeScreen } from './screens/HomeScreen';
import { JourneySetupScreen } from './screens/JourneySetupScreen';
import { PreJourneyCheckScreen } from './screens/PreJourneyCheckScreen';
import { ActiveJourneyScreen } from './screens/ActiveJourneyScreen';
import { EmergencyScreen } from './screens/EmergencyScreen';
import { JourneySummaryScreen } from './screens/JourneySummaryScreen';
import { JourneyHistoryScreen } from './screens/JourneyHistoryScreen';
import { ActivityScreen } from './screens/ActivityScreen';
import { ProfileScreen } from './screens/ProfileScreen';
import { BottomNavigation, NavTab } from './components/BottomNavigation';
import { SOSButton } from './components/SOSButton';

export const App: React.FC = () => {
  const { appState, setAppState, isAuthenticated, triggerManualSOS } = useStreeva();
  const [activeNavTab, setActiveNavTab] = useState<NavTab>('HOME');

  // Synchronize bottom navigation tab with appState changes
  useEffect(() => {
    switch (appState) {
      case 'home':
        setActiveNavTab('HOME');
        break;
      case 'journey_history':
        setActiveNavTab('JOURNEYS');
        break;
      case 'activity':
        setActiveNavTab('ACTIVITY');
        break;
      case 'profile':
        setActiveNavTab('PROFILE');
        break;
    }
  }, [appState]);

  const handleNavSelect = (tab: NavTab) => {
    setActiveNavTab(tab);
    switch (tab) {
      case 'HOME':
        setAppState('home');
        break;
      case 'JOURNEYS':
        setAppState('journey_history');
        break;
      case 'ACTIVITY':
        setAppState('activity');
        break;
      case 'PROFILE':
        setAppState('profile');
        break;
    }
  };

  // Screen Routing Logic
  const renderScreen = () => {
    if (appState === 'splash') {
      return (
        <SplashScreen
          onFinish={() => {
            if (isAuthenticated) {
              setAppState('home');
            } else {
              setAppState('onboarding');
            }
          }}
        />
      );
    }
    if (appState === 'onboarding') {
      return <OnboardingScreen onComplete={() => setAppState('auth')} />;
    }
    if (appState === 'auth') {
      return <AuthScreen />;
    }
    if (appState === 'emergency_countdown' || appState === 'emergency_active') {
      return <EmergencyScreen />;
    }
    if (appState === 'journey_setup') {
      return <JourneySetupScreen />;
    }
    if (appState === 'pre_journey_check') {
      return <PreJourneyCheckScreen />;
    }
    if (appState === 'active_journey') {
      return <ActiveJourneyScreen />;
    }
    if (appState === 'journey_summary') {
      return <JourneySummaryScreen />;
    }
    if (appState === 'journey_history') {
      return <JourneyHistoryScreen />;
    }
    if (appState === 'activity') {
      return <ActivityScreen />;
    }
    if (appState === 'profile') {
      return <ProfileScreen />;
    }

    // Default to Home
    return <HomeScreen />;
  };

  const showBottomNav =
    appState !== 'splash' &&
    appState !== 'onboarding' &&
    appState !== 'auth' &&
    appState !== 'emergency_countdown' &&
    appState !== 'emergency_active';

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(circle at 50% 30%, #131828 0%, #06080E 100%)'
      }}
    >
      {/* Main Mobile App Container Frame */}
      <div className="streeva-app-container">
        {renderScreen()}

        {showBottomNav && (
          <>
            <div
              style={{
                position: 'absolute',
                bottom: '90px',
                right: '18px',
                zIndex: 95
              }}
            >
              <SOSButton onTriggerSOS={triggerManualSOS} size="sm" />
            </div>
            <BottomNavigation
              activeTab={activeNavTab}
              onSelectTab={handleNavSelect}
              onTriggerSOS={triggerManualSOS}
            />
          </>
        )}
      </div>
    </div>
  );
};
