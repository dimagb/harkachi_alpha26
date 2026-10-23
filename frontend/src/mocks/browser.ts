import { setupWorker } from 'msw/browser';
import { createHandlers } from './handlers';

// TODO(lead): учесть штатный eslint-disable в сгенерированном public/mockServiceWorker.js при ревью; исходный файл MSW сохранён без изменений.
export const worker = setupWorker(...createHandlers());
