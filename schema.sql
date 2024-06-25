CREATE TABLE IF NOT EXISTS transactions (
    date BIGINT NOT NULL,
    description VARCHAR NOT NULL,
    amount FLOAT NOT NULL,
    type VARCHAR(20) NOT NULL,
    expense_category VARCHAR(20),
    income BOOL,
    PRIMARY KEY (date, description)
);
