import * as path from 'path';
import { runTests } from '@vscode/test-electron';
import * as os from 'os';
import * as fs from 'fs';

async function main() {
    try {
        console.log('Test run started');

        // Create temporary directory for tests
        const tempWorkspace = path.join(os.tmpdir(), 'vscode-timelapse-test-workspace');
        console.log(`Creating temporary workspace at: ${tempWorkspace}`);
        
        if (fs.existsSync(tempWorkspace)) {
            console.log('Cleaning up existing workspace');
            fs.rmSync(tempWorkspace, { recursive: true, force: true });
        }
        
        fs.mkdirSync(tempWorkspace, { recursive: true });
        console.log('Temporary workspace created');

        // Путь к расширению
        const extensionDevelopmentPath = path.resolve(__dirname, '../../');
        console.log(`Extension development path: ${extensionDevelopmentPath}`);

        // Путь к тестам
        const extensionTestsPath = path.resolve(__dirname, './suite/index');
        console.log(`Extension tests path: ${extensionTestsPath}`);

        console.log('Starting VS Code test instance');
        // Запускаем тесты
        await runTests({
            extensionDevelopmentPath,
            extensionTestsPath,
            launchArgs: [
                tempWorkspace,
                '--disable-extensions',
                '--disable-gpu',
                '--skip-welcome',
                '--skip-release-notes',
                '--disable-telemetry'
            ]
        });
        console.log('Tests completed successfully');

        // Очищаем временную директорию
        console.log('Cleaning up temporary workspace');
        if (fs.existsSync(tempWorkspace)) {
            fs.rmSync(tempWorkspace, { recursive: true, force: true });
        }
        console.log('Cleanup completed');
    } catch (err) {
        console.error('Test run failed:');
        console.error(err);
        process.exit(1);
    }
}

main(); 