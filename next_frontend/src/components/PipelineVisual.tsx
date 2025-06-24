import React from 'react';
import { PipelineStep } from '../types';
import { CheckCircle, Clock, Play, XCircle, ArrowRight } from 'lucide-react';

interface PipelineVisualProps {
  steps: PipelineStep[];
  onStepSelect: (step: PipelineStep) => void;
  selectedStep: PipelineStep | null;
}

const PipelineVisual: React.FC<PipelineVisualProps> = ({ 
  steps, 
  onStepSelect, 
  selectedStep 
}) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'running':
        return <Play className="w-5 h-5 text-blue-600 animate-pulse" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 border-green-300 text-green-800';
      case 'running':
        return 'bg-blue-100 border-blue-300 text-blue-800 animate-pulse';
      case 'failed':
        return 'bg-red-100 border-red-300 text-red-800';
      default:
        return 'bg-gray-100 border-gray-300 text-gray-600';
    }
  };

  const getStepColor = (step: PipelineStep) => {
    const colors: { [key: string]: string } = {
      'init': 'bg-blue-400',
      'dockerfile': 'bg-yellow-400',
      'build': 'bg-gray-600',
      'vm_access': 'bg-green-400',
      'pull_images': 'bg-yellow-400'
    };
    return colors[step.id] || 'bg-gray-400';
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-8">
      <div className="flex items-center justify-center space-x-4 mb-8">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div 
              className={`relative group cursor-pointer transition-all duration-300 ${
                selectedStep?.id === step.id ? 'scale-110' : 'hover:scale-105'
              }`}
              onClick={() => onStepSelect(step)}
            >
              {/* Step Badge */}
              <div className={`
                ${getStepColor(step)} 
                text-white px-4 py-2 rounded-full text-sm font-medium
                shadow-lg transition-all duration-300
                ${selectedStep?.id === step.id ? 'ring-4 ring-blue-200' : ''}
              `}>
                {step.name}
              </div>
              
              {/* Status Indicator */}
              <div className={`
                absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center
                ${getStatusColor(step.status)} border-2
              `}>
                {getStatusIcon(step.status)}
              </div>

              {/* Tooltip */}
              <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10">
                <div className="bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
                  Status: {step.status}
                  {step.duration > 0 && (
                    <span className="ml-2">({step.duration}s)</span>
                  )}
                </div>
              </div>
            </div>

            {/* Arrow connector */}
            {index < steps.length - 1 && (
              <div className="flex items-center">
                <ArrowRight className="w-6 h-6 text-gray-400" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Step Details */}
      {selectedStep && (
        <div className={`
          border-2 rounded-lg p-4 transition-all duration-300
          ${getStatusColor(selectedStep.status)}
        `}>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold">{selectedStep.name}</h3>
            <div className="flex items-center space-x-2">
              {getStatusIcon(selectedStep.status)}
              <span className="text-sm font-medium capitalize">
                {selectedStep.status}
              </span>
            </div>
          </div>
          
          {selectedStep.duration > 0 && (
            <p className="text-sm opacity-75">
              Duration: {selectedStep.duration} seconds
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default PipelineVisual;