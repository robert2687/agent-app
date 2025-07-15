import React, { useState } from 'react';
import DataSourceManagerView from './components/DataSourceManagerView';
import OrchestrationView from './components/OrchestrationView';
import DigitalTwinView from './components/DigitalTwinView';

type View = 'orchestration' | 'datasources' | 'twin';

const TABS: { id: View, name: string, icon: JSX.Element }[] = [
    { id: 'orchestration', name: 'Orchestration', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M10.29 2.221a1 1 0 0 1 1.417 0l2.428 2.513a1 1 0 0 1 .288.702v2.884a1 1 0 0 0 1 1h2.884a1 1 0 0 1 .702.287l2.513 2.428a1 1 0 0 1 0 1.417l-2.513 2.428a1 1 0 0 1-.702.288h-2.884a1 1 0 0 0-1 1v2.884a1 1 0 0 1-.287.702l-2.428 2.513a1 1 0 0 1-1.417 0l-2.428-2.513a1 1 0 0 1-.288-.702v-2.884a1 1 0 0 0-1-1H3.702a1 1 0 0 1-.702-.287L.487 11.713a1 1 0 0 1 0-1.417l2.513-2.428a1 1 0 0 1 .702-.288h2.884a1 1 0 0 0 1-1V4.721a1 1 0 0 1 .287-.702l2.428-2.513Z"/> },
    { id: 'datasources', name: 'Data Sources', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /> },
    { id: 'twin', name: 'Digital Twin', icon: <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" /><path fillRule="evenodd" d="M2.046 9.315a11.332 11.332 0 015.24-4.832 1.5 1.5 0 011.82.235l1.625 1.801a4.5 4.5 0 005.53 0l1.625-1.8a1.5 1.5 0 011.82-.236c2.32.993 4.155 2.827 5.24 5.24a1.5 1.5 0 01-.236 1.82l-1.8 1.625a4.5 4.5 0 000 5.53l1.8 1.625a1.5 1.5 0 01.236 1.82c-.993 2.32-2.827 4.155-5.24 5.24a1.5 1.5 0 01-1.82-.236l-1.625-1.8a4.5 4.5 0 00-5.53 0l-1.625 1.8a1.5 1.5 0 01-1.82.236A11.332 11.332 0 012.046 14.685a1.5 1.5 0 01.236-1.82l1.8-1.625a4.5 4.5 0 000-5.53l-1.8-1.625a1.5 1.5 0 01-.236-1.82zM12 12a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /> },
];

const App: React.FC = () => {
    const [activeView, setActiveView] = useState<View>('orchestration');

    const renderView = () => {
        switch (activeView) {
            case 'orchestration': return <OrchestrationView />;
            case 'datasources': return <DataSourceManagerView />;
            case 'twin': return <DigitalTwinView />;
            default: return <OrchestrationView />;
        }
    };
    
    return (
        <div className="flex h-screen bg-gray-900 text-gray-100 font-sans">
            <nav className="flex flex-col items-center w-20 bg-gray-800 border-r border-gray-700 py-4 space-y-2">
                <div className="text-indigo-400 font-bold text-lg mb-4">AI</div>
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveView(tab.id)}
                        title={tab.name}
                        className={`w-16 h-16 flex flex-col items-center justify-center rounded-lg transition-colors focus:outline-none ${
                            activeView === tab.id
                                ? 'bg-indigo-600 text-white'
                                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                        }`}
                        aria-current={activeView === tab.id ? 'page' : undefined}
                    >
                        <svg className="h-6 w-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                           {tab.icon}
                        </svg>
                        <span className="text-xs mt-1">{tab.name.split(' ')[0]}</span>
                    </button>
                ))}
            </nav>
            <div className="flex-1 flex flex-col overflow-hidden">
                <header className="bg-gray-800 shadow-md px-6 py-3 flex items-center border-b border-gray-700 z-10">
                    <h1 className="text-2xl font-bold text-white tracking-wide">
                        AI <span className="text-indigo-400">App Builder</span>
                    </h1>
                </header>
                <main className="flex-1 overflow-y-auto">
                    {renderView()}
                </main>
                <footer className="text-center p-2 bg-gray-800 border-t border-gray-700">
                    <p className="text-xs text-gray-500">Professional AI Application Builder</p>
                </footer>
            </div>
        </div>
    );
};

export default App;
