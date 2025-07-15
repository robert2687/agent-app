import React from 'react';
import { Agent } from '../types';
import BotIcon from './icons/BotIcon';
import ArchitectureIcon from './icons/ArchitectureIcon';
import BehaviorIcon from './icons/BehaviorIcon';
import DigitalTwinIcon from './icons/DigitalTwinIcon';
import ApiIcon from './icons/ApiIcon';

interface AgentIconProps {
    agent?: Agent;
}

const AgentIcon: React.FC<AgentIconProps> = ({ agent }) => {
    switch (agent) {
        case Agent.SystemsArchitect:
            return <ArchitectureIcon />;
        case Agent.BehavioralModeler:
            return <BehaviorIcon />;
        case Agent.DigitalTwin:
            return <DigitalTwinIcon />;
        case Agent.ApiIntegration:
            return <ApiIcon />;
        case Agent.Default:
        default:
            return <BotIcon />;
    }
};

export default AgentIcon;
