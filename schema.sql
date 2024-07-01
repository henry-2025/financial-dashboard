CREATE TABLE IF NOT EXISTS transactions (
    date BIGINT NOT NULL,
    description VARCHAR NOT NULL,
    type VARCHAR(20) NOT NULL,
    amount FLOAT NOT NULL,
    session_index INT NOT NULL, --the index in the web session
    expense_category VARCHAR(20),
    income BOOL,
    exclude BOOL,
    PRIMARY KEY (date, description)
);
