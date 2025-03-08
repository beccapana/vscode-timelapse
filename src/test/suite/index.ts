import * as path from 'path';
import Mocha from 'mocha';
import { glob } from 'glob';

export async function run(): Promise<void> {
    console.log('Setting up test suite');
    
    // Create Mocha test module
    const mocha = new Mocha({
        ui: 'tdd',
        color: true,
        timeout: 60000 // Увеличиваем таймаут до 60 секунд
    });

    const testsRoot = path.resolve(__dirname, '.');
    console.log(`Tests root directory: ${testsRoot}`);

    try {
        console.log('Searching for test files');
        const files = await glob('**/**.test.js', { cwd: testsRoot });
        console.log(`Found test files: ${files.join(', ')}`);
        
        // Добавляем файлы в тестовый модуль
        files.forEach(f => {
            const testFile = path.resolve(testsRoot, f);
            console.log(`Adding test file: ${testFile}`);
            mocha.addFile(testFile);
        });

        console.log('Starting test run');
        // Запускаем тесты
        return new Promise<void>((resolve, reject) => {
            try {
                mocha.run(failures => {
                    if (failures > 0) {
                        console.error(`Test run completed with ${failures} failures`);
                        reject(new Error(`${failures} tests failed.`));
                    } else {
                        console.log('All tests passed successfully');
                        resolve();
                    }
                });
            } catch (err) {
                console.error('Error during test execution:');
                console.error(err);
                reject(err);
            }
        });
    } catch (err) {
        console.error('Error in test setup:');
        console.error(err);
        throw err;
    }
} 