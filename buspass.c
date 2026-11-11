/* Bus pass management system - data side.

   server.py runs this program for every action and reads the lines it prints,
   so the commands and the output format must stay the same:

     buspass.exe register name age college course year mobile source destination
     buspass.exe search field text
     buspass.exe renew id months
     buspass.exe cancel id reason
     buspass.exe list

   One student is one line of students.txt: 12 fields joined by | and an
   optional 13th reason, used only by cancelled passes:

     STU1001|Name|19|College|Course|Year|Mobile|Source|Destination|Active|01-11-2026|01-02-2027
*/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX 100
#define FEE_PER_MONTH 200

struct Student
{
    char studentID[20];
    char name[50];
    int age;
    char college[100];
    char course[50];
    char year[30];
    char mobile[15];
    char source[50];
    char destination[50];
    char status[10];
    char issueDate[15];
    char expiryDate[15];
    char reason[100];
};

/* ---------- small helpers ---------- */

/* copy value into a field, keep it inside the field size and remove | and
   newlines so one student always stays on one line of the file */
void setText(char *field, int size, char *value)
{
    int i;

    if (value == NULL)
    {
        value = "";
    }

    strncpy(field, value, size - 1);
    field[size - 1] = '\0';

    for (i = 0; field[i] != '\0'; i++)
    {
        if (field[i] == '|' || field[i] == '\n' || field[i] == '\r')
        {
            field[i] = ' ';
        }
    }
}

/* true when the text has no letters or digits at all */
int isBlank(char *text)
{
    for (; *text != '\0'; text++)
    {
        if (!isspace((unsigned char)*text))
        {
            return 0;
        }
    }

    return 1;
}

/* true when every character is a digit */
int digitsOnly(char *text)
{
    for (; *text != '\0'; text++)
    {
        if (!isdigit((unsigned char)*text))
        {
            return 0;
        }
    }

    return 1;
}

/* lowercase copy of the text, so search ignores capital letters */
void makeLower(char *dst, int size, char *src)
{
    int i;

    strncpy(dst, src, size - 1);
    dst[size - 1] = '\0';

    for (i = 0; dst[i] != '\0'; i++)
    {
        dst[i] = tolower((unsigned char)dst[i]);
    }
}

/* print an ERROR line, the web app shows that text to the user */
void fail(char *text)
{
    printf("ERROR: %s\n", text);
}

/* ---------- reading and writing students.txt ---------- */

/* next part of a line split by |, empty text when nothing is left */
char *nextPart(void)
{
    char *part = strtok(NULL, "|");

    if (part == NULL)
    {
        return "";
    }

    return part;
}

/* read one student line into a struct */
void parseLine(struct Student *s, char *line)
{
    setText(s->studentID, sizeof(s->studentID), strtok(line, "|"));
    setText(s->name, sizeof(s->name), nextPart());
    s->age = atoi(nextPart());
    setText(s->college, sizeof(s->college), nextPart());
    setText(s->course, sizeof(s->course), nextPart());
    setText(s->year, sizeof(s->year), nextPart());
    setText(s->mobile, sizeof(s->mobile), nextPart());
    setText(s->source, sizeof(s->source), nextPart());
    setText(s->destination, sizeof(s->destination), nextPart());
    setText(s->status, sizeof(s->status), nextPart());
    setText(s->issueDate, sizeof(s->issueDate), nextPart());
    setText(s->expiryDate, sizeof(s->expiryDate), nextPart());
    setText(s->reason, sizeof(s->reason), nextPart());
}

/* read all students and return how many were found */
int loadStudents(struct Student list[])
{
    int count = 0;
    char line[600];
    FILE *fp = fopen("students.txt", "r");

    if (fp == NULL)
    {
        return 0; // no file yet, so no students yet
    }

    while (fgets(line, sizeof(line), fp) != NULL && count < MAX)
    {
        line[strcspn(line, "\r\n")] = '\0';

        if (line[0] == '\0')
        {
            continue;
        }

        parseLine(&list[count], line);
        count++;
    }

    fclose(fp);
    return count;
}

/* write one student as a | line. the same function is used for the file
   and for the screen, so the two can never drift apart */
void writeStudent(FILE *out, struct Student *s)
{
    fprintf(out, "%s|%s|%d|%s|%s|%s|%s|%s|%s|%s|%s|%s",
            s->studentID, s->name, s->age, s->college, s->course, s->year,
            s->mobile, s->source, s->destination, s->status,
            s->issueDate, s->expiryDate);

    if (s->reason[0] != '\0')
    {
        fprintf(out, "|%s", s->reason);
    }

    fprintf(out, "\n");
}

/* rewrite the whole file, used after a renew or a cancel */
void saveStudents(struct Student list[], int count)
{
    int i;
    FILE *fp = fopen("students.txt", "w");

    if (fp == NULL)
    {
        fail("Cannot open students.txt");
        return;
    }

    for (i = 0; i < count; i++)
    {
        writeStudent(fp, &list[i]);
    }

    fclose(fp);
}

/* ---------- dates (all dates are dd-mm-yyyy text) ---------- */

/* date as a number, -1 when the text is not a date */
time_t parseDate(char *text)
{
    struct tm t = {0};
    int day, month, year;

    if (sscanf(text, "%d-%d-%d", &day, &month, &year) != 3)
    {
        return -1;
    }

    if (day < 1 || day > 31 || month < 1 || month > 12 || year < 2000 || year > 3000)
    {
        return -1;
    }

    t.tm_mday = day;
    t.tm_mon = month - 1;
    t.tm_year = year - 1900;

    return mktime(&t);
}

/* today's date into dst */
void todayText(char *dst, int size)
{
    struct tm *t;
    time_t now = time(NULL);

    t = localtime(&now);
    snprintf(dst, size, "%02d-%02d-%04d", t->tm_mday, t->tm_mon + 1, t->tm_year + 1900);
}

/* add months to a date and write the result into dst.
   mktime fixes the month by itself when it goes past december */
void addMonths(char *dst, int size, char *fromDate, int months)
{
    struct tm *t;
    time_t date = parseDate(fromDate);

    if (date == -1)
    {
        setText(dst, size, "");
        return;
    }

    t = localtime(&date);
    t->tm_mon = t->tm_mon + months;
    mktime(t);
    snprintf(dst, size, "%02d-%02d-%04d", t->tm_mday, t->tm_mon + 1, t->tm_year + 1900);
}

/* ---------- lookups ---------- */

/* position of a student by ID, -1 when not found */
int findStudent(struct Student list[], int count, char *id)
{
    int i;

    for (i = 0; i < count; i++)
    {
        if (strcmp(list[i].studentID, id) == 0)
        {
            return i;
        }
    }

    return -1;
}

/* position of a student by mobile number, used to block duplicates */
int findMobile(struct Student list[], int count, char *mobile)
{
    int i;

    for (i = 0; i < count; i++)
    {
        if (strcmp(list[i].mobile, mobile) == 0)
        {
            return i;
        }
    }

    return -1;
}

/* next free ID into dst. it continues from the biggest ID in the file,
   so it never repeats after a restart */
void nextStudentID(char *dst, struct Student list[], int count)
{
    int i;
    int number = 1000;

    for (i = 0; i < count; i++)
    {
        int num = atoi(&list[i].studentID[3]); // skip the "STU" part

        if (num > number)
        {
            number = num;
        }
    }

    sprintf(dst, "STU%d", number + 1);
}

/* does the student match the chosen field? the text can be a part of the
   value and both sides ignore capital letters */
int fieldMatches(struct Student *s, char *field, char *text)
{
    char textLower[200];
    char valueLower[200];
    char *value = "";

    if (strcmp(field, "id") == 0)
    {
        value = s->studentID;
    }
    else if (strcmp(field, "name") == 0)
    {
        value = s->name;
    }
    else if (strcmp(field, "course") == 0)
    {
        value = s->course;
    }
    else if (strcmp(field, "source") == 0)
    {
        value = s->source;
    }
    else if (strcmp(field, "destination") == 0)
    {
        value = s->destination;
    }
    else
    {
        return 0;
    }

    if (value[0] == '\0')
    {
        return 0;
    }

    makeLower(textLower, sizeof(textLower), text);
    makeLower(valueLower, sizeof(valueLower), value);

    return strstr(valueLower, textLower) != NULL;
}

/* ---------- the four operations ---------- */

/* check a new student and add it to the file.
   status = Active, issue date = today, expiry = today + 3 months.
   on a problem the reason is copied into errorText and 1 is returned */
int addStudent(struct Student list[], int count, struct Student *s, char *errorText)
{
    FILE *fp;

    if (count >= MAX)
    {
        strcpy(errorText, "Sorry, student limit reached");
        return 1;
    }

    if (isBlank(s->name) || s->age <= 0 || isBlank(s->college) || isBlank(s->course) ||
        isBlank(s->year) || isBlank(s->mobile) || isBlank(s->source) || isBlank(s->destination))
    {
        strcpy(errorText, "All fields are required");
        return 1;
    }

    if (s->age < 15 || s->age > 60)
    {
        strcpy(errorText, "Age must be between 15 and 60");
        return 1;
    }

    if (strlen(s->mobile) != 10 || digitsOnly(s->mobile) == 0)
    {
        strcpy(errorText, "Mobile must be exactly 10 digits");
        return 1;
    }

    if (findMobile(list, count, s->mobile) != -1)
    {
        strcpy(errorText, "Mobile number is already registered");
        return 1;
    }

    nextStudentID(s->studentID, list, count);
    setText(s->status, sizeof(s->status), "Active");
    todayText(s->issueDate, sizeof(s->issueDate));
    addMonths(s->expiryDate, sizeof(s->expiryDate), s->issueDate, 3);
    s->reason[0] = '\0';

    // append mode, so the old students are not lost
    fp = fopen("students.txt", "a");

    if (fp == NULL)
    {
        strcpy(errorText, "Cannot open students.txt");
        return 1;
    }

    writeStudent(fp, s);
    fclose(fp);

    return 0;
}

/* renew a pass. the new expiry counts from the old expiry, or from today
   when the pass already expired. returns the position in the list or -1 */
int renewPass(struct Student list[], int count, char *id, int months, char *errorText)
{
    int index;
    char baseDate[15];

    index = findStudent(list, count, id);

    if (index == -1)
    {
        sprintf(errorText, "No student found with ID %s", id);
        return -1;
    }

    // a cancelled pass cannot come back
    if (strcmp(list[index].status, "Cancelled") == 0)
    {
        strcpy(errorText, "This pass is cancelled, cancelled passes cannot be renewed");
        return -1;
    }

    if (months != 1 && months != 3 && months != 6 && months != 12)
    {
        strcpy(errorText, "Months must be 1, 3, 6 or 12");
        return -1;
    }

    if (parseDate(list[index].expiryDate) < time(NULL))
    {
        todayText(baseDate, sizeof(baseDate));
    }
    else
    {
        setText(baseDate, sizeof(baseDate), list[index].expiryDate);
    }

    addMonths(list[index].expiryDate, sizeof(list[index].expiryDate), baseDate, months);
    setText(list[index].status, sizeof(list[index].status), "Active");
    saveStudents(list, count);

    return index;
}

/* cancel a pass. the line stays in the file, only the status and the
   reason change. returns the position in the list or -1 */
int cancelPass(struct Student list[], int count, char *id, char *reason, char *errorText)
{
    int index = findStudent(list, count, id);

    if (index == -1)
    {
        sprintf(errorText, "No student found with ID %s", id);
        return -1;
    }

    if (strcmp(list[index].status, "Cancelled") == 0)
    {
        strcpy(errorText, "This pass is already cancelled");
        return -1;
    }

    if (isBlank(reason))
    {
        strcpy(errorText, "A reason is required to cancel a pass");
        return -1;
    }

    setText(list[index].status, sizeof(list[index].status), "Cancelled");
    setText(list[index].reason, sizeof(list[index].reason), reason);
    saveStudents(list, count);

    return index;
}

/* ---------- the five commands, one per argv[1] ---------- */

void runRegister(struct Student list[], int count, char *args[], int argCount)
{
    struct Student s;
    char errorText[100];

    if (argCount != 8)
    {
        fail("register needs 8 values: name age college course year mobile source destination");
        return;
    }

    setText(s.name, sizeof(s.name), args[0]);
    s.age = atoi(args[1]);
    setText(s.college, sizeof(s.college), args[2]);
    setText(s.course, sizeof(s.course), args[3]);
    setText(s.year, sizeof(s.year), args[4]);
    setText(s.mobile, sizeof(s.mobile), args[5]);
    setText(s.source, sizeof(s.source), args[6]);
    setText(s.destination, sizeof(s.destination), args[7]);

    if (addStudent(list, count, &s, errorText) != 0)
    {
        fail(errorText);
        return;
    }

    writeStudent(stdout, &s);
    printf("OK: Registered\n");
}

void runSearch(struct Student list[], int count, char *args[], int argCount)
{
    int i;
    int found = 0;
    char field[12];
    char text[200];

    if (argCount != 2)
    {
        fail("search needs a field (id, name, course, source, destination) and text");
        return;
    }

    setText(field, sizeof(field), args[0]);
    setText(text, sizeof(text), args[1]);

    if (isBlank(text))
    {
        fail("Search text is empty");
        return;
    }

    for (i = 0; i < count; i++)
    {
        if (fieldMatches(&list[i], field, text))
        {
            writeStudent(stdout, &list[i]);
            found = 1;
        }
    }

    if (found == 0)
    {
        printf("No student found\n");
    }
}

void runRenew(struct Student list[], int count, char *args[], int argCount)
{
    char errorText[100];
    int months;
    int index;

    if (argCount != 2)
    {
        fail("renew needs a Student ID and months (1, 3, 6 or 12)");
        return;
    }

    months = atoi(args[1]);
    index = renewPass(list, count, args[0], months, errorText);

    if (index == -1)
    {
        fail(errorText);
        return;
    }

    writeStudent(stdout, &list[index]);
    printf("OK: Renewed %s for %d months. Fee = Rs %d. New expiry = %s\n",
           list[index].studentID, months, months * FEE_PER_MONTH, list[index].expiryDate);
}

void runCancel(struct Student list[], int count, char *args[], int argCount)
{
    char errorText[100];
    int index;

    if (argCount != 2)
    {
        fail("cancel needs a Student ID and a reason");
        return;
    }

    index = cancelPass(list, count, args[0], args[1], errorText);

    if (index == -1)
    {
        fail(errorText);
        return;
    }

    writeStudent(stdout, &list[index]);
    printf("OK: Cancelled pass %s\n", list[index].studentID);
}

void runList(struct Student list[], int count)
{
    int i;

    for (i = 0; i < count; i++)
    {
        writeStudent(stdout, &list[i]);
    }
}

int main(int argc, char *argv[])
{
    struct Student list[MAX];
    int count = loadStudents(list);

    if (argc < 2)
    {
        fail("Missing command. Use register, search, renew, cancel or list");
        return 1;
    }

    if (strcmp(argv[1], "register") == 0)
    {
        runRegister(list, count, &argv[2], argc - 2);
    }
    else if (strcmp(argv[1], "search") == 0)
    {
        runSearch(list, count, &argv[2], argc - 2);
    }
    else if (strcmp(argv[1], "renew") == 0)
    {
        runRenew(list, count, &argv[2], argc - 2);
    }
    else if (strcmp(argv[1], "cancel") == 0)
    {
        runCancel(list, count, &argv[2], argc - 2);
    }
    else if (strcmp(argv[1], "list") == 0)
    {
        runList(list, count);
    }
    else
    {
        fail("Unknown command. Use register, search, renew, cancel or list");
        return 1;
    }

    return 0;
}
