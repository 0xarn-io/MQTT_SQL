-- v0.1 schema: a single bucket table for every MQTT message we receive.
-- Run once against the target database (e.g. mqtt_sql) before starting the app.

IF OBJECT_ID('dbo.messages', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.messages (
        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
        topic       NVARCHAR(256) NOT NULL,
        received_at DATETIME2     NOT NULL
            CONSTRAINT DF_messages_received_at DEFAULT SYSUTCDATETIME(),
        payload     NVARCHAR(MAX) NOT NULL
    );

    CREATE INDEX IX_messages_received_at ON dbo.messages (received_at DESC);
END;
