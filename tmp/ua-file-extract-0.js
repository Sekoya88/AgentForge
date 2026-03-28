const fs = require('fs');
const path = require('path');

function parsePythonFile(filePath, projectRoot, allProjectFiles) {
    const fullPath = path.join(projectRoot, filePath);
    if (!fs.existsSync(fullPath)) {
        return null;
    }

    const content = fs.readFileSync(fullPath, 'utf-8');
    const lines = content.split('\n');

    const result = {
        path: filePath,
        language: 'python',
        totalLines: lines.length,
        nonEmptyLines: lines.filter(l => l.trim() && !l.trim().startsWith('#')).length,
        functions: [],
        classes: [],
        imports: [],
        exports: [],
        metrics: {
            importCount: 0,
            exportCount: 0,
            functionCount: 0,
            classCount: 0
        }
    };

    let currentClass = null;

    // Simple line-by-line regex parsing for python
    const defRegex = /^\s*async\s+def\s+([a-zA-Z_]\w*)\s*\((.*?)\)/;
    const defSyncRegex = /^\s*def\s+([a-zA-Z_]\w*)\s*\((.*?)\)/;
    const classRegex = /^\s*class\s+([a-zA-Z_]\w*)/;
    const importRegex = /^\s*import\s+([a-zA-Z0-9_\., ]+)/;
    const fromImportRegex = /^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+([a-zA-Z0-9_\., \*]+)/;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lineNo = i + 1;

        // Functions
        const defMatch = line.match(defRegex) || line.match(defSyncRegex);
        if (defMatch) {
            const name = defMatch[1];
            const params = defMatch[2].split(',').map(p => p.split(':')[0].trim()).filter(Boolean);

            // If it's indented, it's likely a method
            const isMethod = /^\s+/.test(line);
            if (isMethod && currentClass) {
                currentClass.methods.push(name);
            } else if (!isMethod) {
                result.functions.push({
                    name,
                    startLine: lineNo,
                    endLine: lineNo, // Rough estimate
                    params
                });
                result.metrics.functionCount++;

                if (!name.startsWith('_')) {
                    result.exports.push({ name, line: lineNo, isDefault: false });
                    result.metrics.exportCount++;
                }
            }
        }

        // Classes
        const classMatch = line.match(classRegex);
        if (classMatch) {
            const name = classMatch[1];
            currentClass = {
                name,
                startLine: lineNo,
                endLine: lineNo, // Rough estimate
                methods: [],
                properties: []
            };
            result.classes.push(currentClass);
            result.metrics.classCount++;

            if (!name.startsWith('_')) {
                result.exports.push({ name, line: lineNo, isDefault: false });
                result.metrics.exportCount++;
            }
        }

        // Reset class context if we hit a top-level definition or import
        if (/^[a-zA-Z]/.test(line) && !classMatch && !defMatch) {
            currentClass = null;
        }

        // Imports
        const importMatch = line.match(importRegex);
        if (importMatch) {
            const mods = importMatch[1].split(',').map(m => m.trim());
            for (const mod of mods) {
                let resolvedPath = null;
                // Python absolute import from project root
                const pyPath = mod.replace(/\./g, '/') + '.py';
                const pyInitPath = mod.replace(/\./g, '/') + '/__init__.py';

                // Very naive resolution for python assuming "app.x"
                const candidate1 = path.join('backend', pyPath);
                const candidate2 = path.join('backend', pyInitPath);

                if (allProjectFiles.includes(candidate1)) resolvedPath = candidate1;
                else if (allProjectFiles.includes(candidate2)) resolvedPath = candidate2;

                result.imports.push({
                    source: mod,
                    resolvedPath,
                    specifiers: [mod],
                    line: lineNo,
                    isExternal: !resolvedPath
                });
                result.metrics.importCount++;
            }
        }

        const fromImportMatch = line.match(fromImportRegex);
        if (fromImportMatch) {
            const source = fromImportMatch[1];
            const specifiers = fromImportMatch[2].split(',').map(m => m.trim());

            let resolvedPath = null;
            // Attempt resolving
            const pyPath = source.replace(/\./g, '/') + '.py';
            const pyInitPath = source.replace(/\./g, '/') + '/__init__.py';

            // Assume backend is the root package container for these files
            const candidate1 = path.join('backend', pyPath);
            const candidate2 = path.join('backend', pyInitPath);

            if (source.startsWith('.')) {
                // relative import logic - skipped for brevity, just mark unresolved/external
            } else if (allProjectFiles.includes(candidate1)) {
                resolvedPath = candidate1;
            } else if (allProjectFiles.includes(candidate2)) {
                resolvedPath = candidate2;
            }

            result.imports.push({
                source,
                resolvedPath,
                specifiers,
                line: lineNo,
                isExternal: !resolvedPath
            });
            result.metrics.importCount++;
        }
    }

    return result;
}

function main() {
    const args = process.argv.slice(2);
    if (args.length < 2) process.exit(1);

    const inputPath = args[0];
    const outputPath = args[1];

    const inputData = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
    const { projectRoot, allProjectFiles, batchFiles } = inputData;

    const output = {
        scriptCompleted: true,
        filesAnalyzed: 0,
        filesSkipped: [],
        results: []
    };

    for (const file of batchFiles) {
        const res = parsePythonFile(file.path, projectRoot, allProjectFiles || []);
        if (res) {
            output.results.push(res);
            output.filesAnalyzed++;
        } else {
            output.filesSkipped.push(file.path);
        }
    }

    fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
}

main();
