FROM php:8.3-apache
RUN a2enmod rewrite && sed -ri 's/AllowOverride None/AllowOverride All/g' /etc/apache2/apache2.conf
COPY . /var/www/html/
RUN mkdir -p /var/www/html/private && chown -R www-data:www-data /var/www/html/private && chmod 770 /var/www/html/private
EXPOSE 80
