# …или создайте новый репозиторий в командной строке
```
echo "# Rutube_Pilot" >> README.md 
git init 
git add README.md 
git commit -m "first commit" 
git branch -M main 
git remote add origin https://github.com/Bogdanov1985/Rutube_Pilot.git
git push -u origin main
```

# …или отправить изменения в существующий репозиторий из командной строки
```
git remote add origin https://github.com/Bogdanov1985/Rutube_Pilot.git
git branch -M main 
git push -u origin main
```