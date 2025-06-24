import React from 'react';
import { PipelineStep } from '../types';
import { Terminal, Copy, Download } from 'lucide-react';

interface OutputPanelProps {
  step: PipelineStep | null;
}

const OutputPanel: React.FC<OutputPanelProps> = ({ step }) => {
  const copyToClipboard = () => {
    if (step?.output) {
      navigator.clipboard.writeText(step.output);
    }
  };

  if (!step) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-8">
        <div className="text-center text-gray-500">
          <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Select a pipeline step to view output</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-900 text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Terminal className="w-5 h-5" />
          <span className="font-medium">Output</span>
        </div>
        <div className="flex items-center space-x-2">
          <button 
            onClick={copyToClipboard}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
            title="Copy to clipboard"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button 
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
            title="Download output"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {step.name}
          </h3>
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
            step.status === 'completed' ? 'bg-green-100 text-green-800' :
            step.status === 'running' ? 'bg-blue-100 text-blue-800' :
            step.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {step.status}
          </div>
        </div>

        {step.output ? (
          <div className="bg-gray-900 rounded-lg p-4 overflow-auto max-h-96">
            <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
              {step.output}
            </pre>
          </div>
        ) : (
          <div className="bg-gray-50 rounded-lg p-8 text-center">
            <div className="text-gray-400 mb-2">
              {step.status === 'running' ? (
                <div className="flex items-center justify-center space-x-2">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  <span>Executing step...</span>
                </div>
              ) : (
                <span>No output available yet</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OutputPanel;