CREATE USER IF NOT EXISTS 'soporte_user'@'localhost' IDENTIFIED BY 'soporte_password';
CREATE USER IF NOT EXISTS 'soporte_user'@'%' IDENTIFIED BY 'soporte_password';
SELECT User, Host FROM mysql.user;
