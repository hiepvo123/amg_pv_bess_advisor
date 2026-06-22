export class PowerPredictions {
    url;
    resultJSON = [];

    constructor(url) {
        this.url = url;

    }

    async load() {
        const response = await fetch(this.url);
        const csv = await response.text();
        
        this.parseFileToJSON(csv);
    }

    parseFileToJSON(csv) {
        const lines = csv.trim().split('\n');
        const headers = lines[0].split(',');

        this.resultJSON = lines.slice(1).map(line => {
            const values = line.split(',');

            return headers.reduce((obj, header, i) => {
                let value = values[i];

                if (value === 'True') value = true;
                else if (value === 'False') value = false;
                else if (!isNaN(value) && value !== '') value = Number(value);

                obj[header] = value;
                return obj;
            }, {});
        });

    }
}