
import React, { useState, useCallback } from 'react';
import { generateImages } from '../services/geminiService';
import { Spinner } from './ui/Spinner';

const ImageView: React.FC = () => {
    const [prompt, setPrompt] = useState('A photorealistic image of a cat wearing a tiny wizard hat, sitting on a pile of ancient books.');
    const [images, setImages] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = useCallback(async (e: React.FormEvent) => {
        e.preventDefault();
        if (!prompt.trim() || isLoading) return;

        setIsLoading(true);
        setError(null);
        setImages([]);

        try {
            const generated = await generateImages(prompt);
            setImages(generated);
        } catch (err) {
            console.error(err);
            const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
            setError(`Failed to generate images: ${errorMessage}`);
        } finally {
            setIsLoading(false);
        }
    }, [prompt, isLoading]);

    return (
        <div className="p-4 sm:p-6 md:p-8 h-full flex flex-col">
            <div className="text-center mb-6">
                <h2 className="text-3xl font-bold text-white">Image Generation</h2>
                <p className="text-gray-400 mt-2">Describe an image and let AI bring it to life.</p>
            </div>
            
            <form onSubmit={handleGenerate} className="w-full max-w-2xl mx-auto mb-6">
                <div className="flex flex-col sm:flex-row items-center gap-2">
                    <input
                        type="text"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="e.g., A robot holding a red skateboard"
                        disabled={isLoading}
                        className="flex-1 w-full p-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !prompt.trim()}
                        className="w-full sm:w-auto px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors flex justify-center items-center"
                    >
                        {isLoading ? <Spinner /> : 'Generate'}
                    </button>
                </div>
            </form>
            
            {error && (
                <div className="text-center p-4 my-4 text-sm text-red-400 bg-red-900/50 rounded-md max-w-2xl mx-auto">
                    {error}
                </div>
            )}

            <div className="flex-1 overflow-y-auto">
                {isLoading && (
                    <div className="flex justify-center items-center h-full">
                        <div className="text-center">
                           <Spinner size="lg"/>
                           <p className="mt-4 text-gray-400">Generating your masterpiece... this may take a moment.</p>
                        </div>
                    </div>
                )}
                
                {!isLoading && images.length === 0 && (
                    <div className="flex justify-center items-center h-full">
                        <div className="text-center text-gray-500">
                            <svg xmlns="http://www.w3.org/2000/svg" className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <p className="mt-4">Your generated images will appear here.</p>
                        </div>
                    </div>
                )}

                {images.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-4">
                        {images.map((base64Image, index) => (
                            <div key={index} className="aspect-square bg-gray-800 rounded-lg overflow-hidden shadow-lg transform hover:scale-105 transition-transform duration-300">
                                <img
                                    src={`data:image/jpeg;base64,${base64Image}`}
                                    alt={`Generated image ${index + 1}`}
                                    className="w-full h-full object-cover"
                                />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ImageView;
